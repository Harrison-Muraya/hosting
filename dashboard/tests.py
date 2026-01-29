from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import uuid
import logging

# Assuming these are your models - adjust imports as needed
from .models import User, Service, Invoice, Plan
from .proxmox import ProxmoxManager

logger = logging.getLogger(__name__)


@shared_task
def send_welcome_email(user_id):
    """Send welcome email to new user"""
    try:
        user = User.objects.get(id=user_id)
        subject = 'Welcome to HostPro!'
        message = f"""
Hello {user.first_name}!

Welcome to HostPro - Your Professional Hosting Solution!

Thank you for registering with us. Your account has been successfully created.

Account Details:
- Username: {user.username}
- Email: {user.email}
- Account Balance: ${user.balance}

Getting Started:
1. Browse our hosting plans
2. Select a plan that suits your needs
3. Make payment via M-Pesa or PayPal
4. Your VM will be deployed automatically

Need help? Contact our support team anytime.

Best regards,
The HostPro Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        
        logger.info(f"Welcome email sent to {user.email}")
        return {'status': 'success', 'message': f'Welcome email sent to {user.email}'}
        
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        return {'status': 'error', 'message': 'User not found'}
    except Exception as e:
        logger.error(f"Failed to send welcome email: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def send_vm_deployment_failed_email(service_id, error_message):
    """Send email when VM deployment fails"""
    try:
        service = Service.objects.get(id=service_id)
        subject = '⚠️ Service Deployment Issue'
        message = f"""
Hello {service.user.first_name},

We encountered an issue while deploying your {service.plan.name} service.

Error Details:
{error_message}

Our technical team has been notified and is working to resolve this issue.
We'll have your service up and running as soon as possible.

Your payment has been processed successfully, and your service will be activated 
once the technical issue is resolved.

If you have any questions, please don't hesitate to contact our support team.

Best regards,
The HostPro Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [service.user.email],
            fail_silently=False,
        )
        
        # Also notify admin
        if hasattr(settings, 'ADMIN_EMAIL'):
            admin_message = f"""
VM Deployment Failed:

Service ID: {service_id}
User: {service.user.username} ({service.user.email})
Plan: {service.plan.name}
Error: {error_message}

Please investigate and resolve.
            """
            send_mail(
                f'[URGENT] VM Deployment Failed - Service {service_id}',
                admin_message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.ADMIN_EMAIL],
                fail_silently=True,
            )
        
        logger.info(f"Deployment failure email sent for service {service_id}")
        return {'status': 'success'}
        
    except Exception as e:
        logger.error(f"Failed to send deployment failure email: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def send_service_credentials_email(service_id):
    """Send service credentials to user"""
    try:
        service = Service.objects.get(id=service_id)
        subject = f'🎉 Your {service.plan.name} Service is Ready!'
        
        site_url = getattr(settings, 'SITE_URL', 'https://your-site.com')
        
        message = f"""
Hello {service.user.first_name}!

Great news! Your {service.plan.name} service has been successfully activated and deployed!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🖥️  SERVICE DETAILS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

VM ID: {service.vm_id}
Plan: {service.plan.name}
Status: Active ✓

📊 RESOURCES:
- CPU Cores: {service.plan.cpu_cores}
- RAM: {service.plan.ram_mb}MB
- Disk: {service.plan.disk_gb}GB SSD
- Bandwidth: {service.plan.bandwidth_gb}GB

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔐 SSH ACCESS CREDENTIALS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

IP Address: {service.ip_address or 'Pending...'}
Username: {service.username}
Password: {service.password}

SSH Command:
ssh {service.username}@{service.ip_address}

⚠️  IMPORTANT: Change your root password immediately after first login!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 BILLING INFORMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Billing Cycle: {service.billing_cycle.title()}
Amount: ${service.price}
Next Due Date: {service.next_due_date.strftime('%B %d, %Y')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📱 MANAGE YOUR SERVICE:
View your dashboard: {site_url}/dashboard/

Need help? Contact our support team anytime!

Best regards,
The HostPro Team

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [service.user.email],
            fail_silently=False,
        )
        
        logger.info(f"Credentials email sent for service {service_id}")
        return {'status': 'success'}
        
    except Exception as e:
        logger.error(f"Failed to send credentials email for service {service_id}: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def check_service_renewals():
    """Check for services that need renewal"""
    try:
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
        
        logger.info(f"Processed {services.count()} services for renewal")
        return {'status': 'success', 'count': services.count()}
        
    except Exception as e:
        logger.error(f"Failed to check service renewals: {str(e)}")
        return {'status': 'error', 'message': str(e)}


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
The HostPro Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [service.user.email],
            fail_silently=False,
        )
        
        logger.info(f"Renewal reminder sent for service {service_id}")
        return {'status': 'success'}
        
    except Exception as e:
        logger.error(f"Failed to send renewal reminder: {str(e)}")
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
        
        logger.info(f"Service {service_id} suspended")
        return {'status': 'success'}
        
    except Exception as e:
        logger.error(f"Failed to suspend service {service_id}: {str(e)}")
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
The HostPro Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [service.user.email],
            fail_silently=False,
        )
        
        logger.info(f"Suspension email sent for service {service_id}")
        return {'status': 'success'}
        
    except Exception as e:
        logger.error(f"Failed to send suspension email: {str(e)}")
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
        
        logger.info(f"Service {service_id} reactivated")
        return {'status': 'success'}
        
    except Exception as e:
        logger.error(f"Failed to reactivate service {service_id}: {str(e)}")
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
        
        logger.info(f"Service {service_id} terminated")
        return {'status': 'success'}
        
    except Exception as e:
        logger.error(f"Failed to terminate service {service_id}: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def check_suspended_services():
    """Check and terminate long-suspended services"""
    try:
        # Terminate services suspended for more than 7 days
        termination_threshold = timezone.now() - timedelta(days=7)
        
        services = Service.objects.filter(
            status='suspended',
            suspended_at__lte=termination_threshold
        )
        
        for service in services:
            terminate_service_task.delay(service.id)
        
        logger.info(f"Queued {services.count()} suspended services for termination")
        return {'status': 'success', 'count': services.count()}
        
    except Exception as e:
        logger.error(f"Failed to check suspended services: {str(e)}")
        return {'status': 'error', 'message': str(e)}