from celery import shared_task
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from core.models import Service
from django.contrib.auth import get_user_model
from vms.proxmox import ProxmoxManager
from payments.models import Invoice, Transaction
import uuid
import logging



User = get_user_model()
logger = logging.getLogger(__name__)

# Welcome email task
@shared_task
def send_welcome_email(user_id):
    """Send welcome email to new user"""
    try:
        user = User.objects.get(id=user_id)
        
        subject = 'Welcome to HostPro!'
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = [user.email]

        # context for email template
        context = {
            'name': user.first_name,
            'email': user.email,
            'username': user.username,
            'year': timezone.now().year,
            'balance': user.balance,
        }

        # Render HTML template
        html_content = render_to_string('emails/welcome_email.html', context)
        text_content = f"Welcome to HostPro, {user.first_name}! Your account has been created successfully."
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=to_email
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
        
        return {'status': 'success', 'message': f'Welcome email sent to {user.email}'}
    except User.DoesNotExist:
        return {'status': 'error', 'message': 'User not found'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}  


@shared_task
# def create_vm_task(service_id):
#     """
#     Create VM for a service - REAL IMPLEMENTATION
#     """
#     logger.info(f"Starting VM creation for service {service_id}")
    
#     try:
#         service = Service.objects.get(id=service_id)
#         proxmox = ProxmoxManager()
        
#         # Test Proxmox connection first
#         connection_test = proxmox.test_connection()
#         if connection_test['status'] != 'success':
#             logger.error(f"Proxmox connection failed: {connection_test['message']}")
#             service.status = 'suspended'
#             service.save()
#             send_vm_deployment_failed_email.delay(service_id, connection_test['message'])
#             return {
#                 'status': 'error',
#                 'message': 'Proxmox connection failed'
#             }
        
#         # Get next VM ID
#         vmid = proxmox.get_next_vmid()
#         vm_name = f"vps-{service.user.username}-{vmid}"
        
#         logger.info(f"Creating VM {vmid} for service {service_id}")
#         logger.info(f"Specs: {service.plan.cpu_cores} cores, {service.plan.ram_mb}MB RAM, {service.plan.disk_gb}GB disk")
        
#         # Create the VM
#         template_id = getattr(settings, 'PROXMOX_TEMPLATE_ID', None)
#         result = proxmox.create_vm(
#             vmid=vmid,
#             name=vm_name,
#             cores=service.plan.cpu_cores,
#             memory=service.plan.ram_mb,
#             disk=service.plan.disk_gb,
#             template_id=template_id
#         )
        
#         if result['status'] == 'success':
#             # Generate credentials
#             password = proxmox.generate_password()
            
#             # Update service
#             service.vm_id = vmid
#             service.ip_address = result.get('ip_address')
#             service.username = 'root'
#             service.password = password
#             service.status = 'active'
#             service.activated_at = timezone.now()
#             service.save()
            
#             logger.info(f"VM {vmid} created successfully for service {service_id}")
#             logger.info(f"IP Address: {service.ip_address}")
            
#             # Send email with credentials
#             send_service_credentials_email.delay(service_id)
            
#             return {
#                 'status': 'success',
#                 'vmid': vmid,
#                 'ip_address': service.ip_address,
#                 'message': 'VM created successfully'
#             }
#         else:
#             logger.error(f"VM creation failed for service {service_id}: {result['message']}")
#             service.status = 'suspended'
#             service.save()
            
#             # Send failure email
#             send_vm_deployment_failed_email.delay(service_id, result['message'])
            
#             return result
            
#     except Service.DoesNotExist:
#         logger.error(f"Service {service_id} not found")
#         return {'status': 'error', 'message': 'Service not found'}
#     except Exception as e:
#         logger.error(f"Exception during VM creation for service {service_id}: {str(e)}")
#         try:
#             service = Service.objects.get(id=service_id)
#             service.status = 'suspended'
#             service.save()
#             send_vm_deployment_failed_email.delay(service_id, str(e))
#         except:
#             pass
#         return {'status': 'error', 'message': str(e)}

# Updated create_vm_task with password generation before VM creation
@shared_task 
def create_vm_task(service_id):
    """
    Create VM for a service - REAL IMPLEMENTATION
    """
    logger.info(f"Starting VM creation for service {service_id}")
    
    try:
        service = Service.objects.get(id=service_id)
        proxmox = ProxmoxManager()
        
        # Test connection
        connection_test = proxmox.test_connection()
        if connection_test['status'] != 'success':
            logger.error(f"Proxmox connection failed: {connection_test['message']}")
            service.status = 'suspended'
            service.save()
            send_vm_deployment_failed_email.delay(service_id, connection_test['message'])
            return {'status': 'error', 'message': 'Proxmox connection failed'}
        
        # Get next VM ID
        vmid = proxmox.get_next_vmid()
        vm_name = f"vps-{service.user.username}-{vmid}"
        
        # Generate password BEFORE creating VM
        password = proxmox.generate_password()
        
        logger.info(f"Creating VM {vmid} for service {service_id}")
        logger.info(f"Specs: {service.plan.cpu_cores} cores, {service.plan.ram_mb}MB RAM, {service.plan.disk_gb}GB disk")
        
        # Create the VM with password
        template_id = getattr(settings, 'PROXMOX_TEMPLATE_ID', None)
        result = proxmox.create_vm(
            vmid=vmid,
            name=vm_name,
            cores=service.plan.cpu_cores,
            memory=service.plan.ram_mb,
            disk=service.plan.disk_gb,
            template_id=template_id,
            password=password  # Pass the password here
        )
        
        if result['status'] == 'success':
            # Update service with credentials
            service.vm_id = vmid
            service.ip_address = result.get('ip_address')
            service.username = 'root'
            service.password = password  # Save the generated password
            service.status = 'active'
            service.activated_at = timezone.now()
            service.save()
            
            logger.info(f"VM {vmid} created successfully for service {service_id}")
            logger.info(f"IP Address: {service.ip_address}")
            
            # Send email with credentials
            send_service_credentials_email.delay(service_id)
            
            return {
                'status': 'success',
                'vmid': vmid,
                'ip_address': service.ip_address,
                'message': 'VM created successfully'
            }
        else:
            logger.error(f"VM creation failed for service {service_id}: {result['message']}")
            service.status = 'suspended'
            service.save()
            send_vm_deployment_failed_email.delay(service_id, result['message'])
            return result
            
    except Service.DoesNotExist:
        logger.error(f"Service {service_id} not found")
        return {'status': 'error', 'message': 'Service not found'}
    except Exception as e:
        logger.error(f"Exception during VM creation for service {service_id}: {str(e)}")
        try:
            service = Service.objects.get(id=service_id)
            service.status = 'suspended'
            service.save()
            send_vm_deployment_failed_email.delay(service_id, str(e))
        except:
            pass
        return {'status': 'error', 'message': str(e)}

# Send VM deployment failure email
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
        
        return {'status': 'success'}
    except Exception as e:
        logger.error(f"Failed to send deployment failure email: {str(e)}")
        return {'status': 'error', 'message': str(e)}

# Check service renewals task
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
    
# @shared_task
# def send_service_credentials_email(service_id):
#     """Send service credentials to user"""
#     try:
#         service = Service.objects.get(id=service_id)
        
#         subject = f'🎉 Your {service.plan.name} Service is Ready!'
#         message = f"""
# Hello {service.user.first_name}!

# Great news! Your {service.plan.name} service has been successfully activated and deployed!

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🖥️  SERVICE DETAILS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# VM ID: {service.vm_id}
# Plan: {service.plan.name}
# Status: Active ✓

# 📊 RESOURCES:
# • CPU Cores: {service.plan.cpu_cores}
# • RAM: {service.plan.ram_mb}MB
# • Disk: {service.plan.disk_gb}GB SSD
# • Bandwidth: {service.plan.bandwidth_gb}GB

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔐 SSH ACCESS CREDENTIALS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# IP Address: {service.ip_address or 'Pending...'}
# Username: {service.username}
# Password: {service.password}

# SSH Command:
# ssh {service.username}@{service.ip_address}

# ⚠️ IMPORTANT: Change your root password immediately after first login!

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 💰 BILLING INFORMATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Billing Cycle: {service.billing_cycle.title()}
# Amount: ${service.price}
# Next Due Date: {service.next_due_date.strftime('%B %d, %Y')}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 📱 MANAGE YOUR SERVICE:
# View your dashboard: {settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'https://your-site.com'}/dashboard/

# Need help? Contact our support team anytime!

# Best regards,
# The HostPro Team

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#         """
        
#         send_mail(
#             subject,
#             message,
#             settings.DEFAULT_FROM_EMAIL,
#             [service.user.email],
#             fail_silently=False,
#         )
        
#         logger.info(f"Credentials email sent for service {service_id}")
#         return {'status': 'success'}
#     except Exception as e:
#         logger.error(f"Failed to send credentials email for service {service_id}: {str(e)}")
#         return {'status': 'error', 'message': str(e)}

@shared_task
def send_service_credentials_email(service_id):
    """Send service credentials to user"""
    try:
        service = Service.objects.get(id=service_id)
        
        subject = f'🎉 Your {service.plan.name} Service is Ready!'
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = [service.user.email]

        # context for email template
        context = {
            'name': service.user.first_name,
            'plan_name': service.plan.name,
            'vm_id': service.vm_id,
            'ip_address': service.ip_address or 'Pending...',
            'username': service.username,
            'password': service.password,
            'cpu': service.plan.cpu_cores,
            'ram': service.plan.ram_mb,
            'disk': service.plan.disk_gb,
            'bandwidth': service.plan.bandwidth_gb,
            'billing_cycle': service.billing_cycle.title(),
            'amount': service.price,
            'next_due_date': service.next_due_date.strftime('%B %d, %Y'),
            'dashboard_url': f"{getattr(settings, 'SITE_URL', 'https://your-site.com')}/dashboard/",
            'year': timezone.now().year, 
        }

        # Render HTML template
        html_content = render_to_string('emails/service_credentials.html', context)

        text_content = f"Your {service.plan.name} service is ready. Please check your email for details."
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=to_email
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
        logger.info(f"Credentials email sent for service {service_id}")
        return {'status': 'success'}
    except Exception as e:
        logger.error(f"Failed to send credentials email for service {service_id}: {str(e)}")
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