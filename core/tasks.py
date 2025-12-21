from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from core.models import Service, User
from vms.proxmox import ProxmoxManager
from payments.models import Invoice, Transaction
import uuid

@shared_task
def create_vm_task(service_id):
    """Create VM for a service"""
    try:
        service = Service.objects.get(id=service_id)
        proxmox = ProxmoxManager()
        
        vmid = proxmox.get_next_vmid()
        vm_name = f"vm-{service.user.username}-{vmid}"
        
        result = proxmox.create_vm(
            vmid=vmid,
            name=vm_name,
            cores=service.plan.cpu_cores,
            memory=service.plan.ram_mb,
            disk=service.plan.disk_gb
        )
        
        if result['status'] == 'success':
            password = proxmox.generate_password()
            service.vm_id = vmid
            service.ip_address = result.get('ip_address')
            service.username = 'root'
            service.password = password
            service.status = 'active'
            service.activated_at = timezone.now()
            service.save()
            
            # Send email with credentials
            send_service_credentials_email.delay(service_id)
            
        return result
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

@shared_task
def send_service_credentials_email(service_id):
    """Send service credentials to user"""
    try:
        service = Service.objects.get(id=service_id)
        
        subject = f'Your {service.plan.name} Service is Ready'
        message = f"""
        Hello {service.user.first_name},
        
        Your {service.plan.name} service has been activated!
        
        Service Details:
        - IP Address: {service.ip_address}
        - Username: {service.username}
        - Password: {service.password}
        - Next Due Date: {service.next_due_date.strftime('%Y-%m-%d')}
        
        You can manage your service from your dashboard.
        
        Best regards,
        Hosting Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [service.user.email],
            fail_silently=False,
        )
        
        return {'status': 'success'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

@shared_task
def check_service_renewals():
    """Check for services that need renewal"""
    tomorrow = timezone.now() + timedelta(days=1)
    services = Service.objects.filter(
        status='active',
        next_due_date__lte=tomorrow
    )
    
    for service in services:
        # Create invoice
        invoice = Invoice.objects.create(
            user=service.user,
            service=service,
            invoice_number=f'INV-{uuid.uuid4().hex[:8].upper()}',
            amount=service.price,
            due_date=service.next_due_date,
            description=f'Renewal for {service.plan.name}'
        )
        
        # Send reminder email
        send_renewal_reminder_email.delay(service.id, invoice.id)
        
        # If past due date, suspend service
        if service.next_due_date < timezone.now():
            suspend_service_task.delay(service.id)

@shared_task
def send_renewal_reminder_email(service_id, invoice_id):
    """Send renewal reminder email"""
    try:
        service = Service.objects.get(id=service_id)
        invoice = Invoice.objects.get(id=invoice_id)
        
        subject = f'Service Renewal Due - {service.plan.name}'
        message = f"""
        Hello {service.user.first_name},
        
        Your {service.plan.name} service is due for renewal.
        
        Invoice: {invoice.invoice_number}
        Amount: ${invoice.amount}
        Due Date: {invoice.due_date.strftime('%Y-%m-%d')}
        
        Please make payment to avoid service suspension.
        
        Best regards,
        Hosting Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [service.user.email],
            fail_silently=False,
        )
        
        return {'status': 'success'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

@shared_task
def suspend_service_task(service_id):
    """Suspend a service"""
    try:
        service = Service.objects.get(id=service_id)
        proxmox = ProxmoxManager()
        
        if service.vm_id:
            proxmox.stop_vm(service.vm_id)
        
        service.status = 'suspended'
        service.suspended_at = timezone.now()
        service.save()
        
        # Send suspension email
        send_suspension_email.delay(service_id)
        
        return {'status': 'success'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

@shared_task
def send_suspension_email(service_id):
    """Send service suspension email"""
    try:
        service = Service.objects.get(id=service_id)
        
        subject = f'Service Suspended - {service.plan.name}'
        message = f"""
        Hello {service.user.first_name},
        
        Your {service.plan.name} service has been suspended due to non-payment.
        
        Please make payment immediately to reactivate your service.
        
        Best regards,
        Hosting Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [service.user.email],
            fail_silently=False,
        )
        
        return {'status': 'success'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

@shared_task
def reactivate_service_task(service_id):
    """Reactivate a suspended service"""
    try:
        service = Service.objects.get(id=service_id)
        proxmox = ProxmoxManager()
        
        if service.vm_id:
            proxmox.start_vm(service.vm_id)
        
        service.status = 'active'
        service.suspended_at = None
        service.next_due_date = service.calculate_next_due_date()
        service.save()
        
        return {'status': 'success'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

@shared_task
def terminate_service_task(service_id):
    """Terminate a service"""
    try:
        service = Service.objects.get(id=service_id)
        proxmox = ProxmoxManager()
        
        if service.vm_id:
            proxmox.delete_vm(service.vm_id)
        
        service.status = 'terminated'
        service.terminated_at = timezone.now()
        service.save()
        
        return {'status': 'success'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

@shared_task
def check_suspended_services():
    """Check services suspended for more than 7 days and terminate them"""
    week_ago = timezone.now() - timedelta(days=7)
    services = Service.objects.filter(
        status='suspended',
        suspended_at__lte=week_ago
    )
    
    for service in services:
        terminate_service_task.delay(service.id)