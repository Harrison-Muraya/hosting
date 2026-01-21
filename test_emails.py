import os
import sys
import django
import time
from datetime import timedelta
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hosting.settings')  # Change to your project name
django.setup()

from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from core.models import Service, Plan
from payments.models import Invoice
from core.tasks import (
    send_welcome_email,
    send_service_credentials_email,
    send_vm_deployment_failed_email,
    send_renewal_reminder_email,
    send_suspension_email
)

User = get_user_model()


class EmailTester:
    """Test all email tasks with Mailtrap"""
    
    def __init__(self):
        self.test_user = None
        self.test_plan = None
        self.test_service = None
        self.test_invoice = None
        self.results = []
        
    def setup(self):
        """Create test data"""
        print("\n" + "="*60)
        print("SETTING UP TEST DATA")
        print("="*60)
        
        # Create or get test user
        self.test_user, created = User.objects.get_or_create(
            username='testuser_mailtrap',
            defaults={
                'email': 'test@example.com',  # This will go to Mailtrap
                'first_name': 'Test',
                'last_name': 'User',
                'balance': Decimal('50.00')
            }
        )
        if created:
            self.test_user.set_password('testpass123')
            self.test_user.save()
        print(f"✓ Test user created/found: {self.test_user.username}")
        
        # Create or get test plan
        self.test_plan, created = Plan.objects.get_or_create(
            name='Test VPS Plan',
            defaults={
                'cpu_cores': 2,
                'ram_mb': 2048,
                'disk_gb': 50,
                'bandwidth_gb': 1000,
                'price_monthly': Decimal('10.00'),
                'price_quarterly': Decimal('27.00'),
                'price_annually': Decimal('100.00'),
                'is_active': True
            }
        )
        print(f"✓ Test plan created/found: {self.test_plan.name}")
        
        # Create or get test service
        self.test_service, created = Service.objects.get_or_create(
            user=self.test_user,
            plan=self.test_plan,
            defaults={
                'billing_cycle': 'monthly',
                'price': Decimal('10.00'),
                'status': 'active',
                'vm_id': 12345,
                'ip_address': '192.168.1.100',
                'username': 'root',
                'password': 'TestPass123!',
                'activated_at': timezone.now(),
                'next_due_date': timezone.now() + timedelta(days=30)
            }
        )
        print(f"✓ Test service created/found: ID {self.test_service.id}")
        
        # Create test invoice
        self.test_invoice, created = Invoice.objects.get_or_create(
            user=self.test_user,
            service=self.test_service,
            defaults={
                'invoice_number': 'TEST-INV-001',
                'amount': Decimal('10.00'),
                'due_date': timezone.now() + timedelta(days=7),
                'description': f'Renewal for {self.test_plan.name}',
                'status': 'unpaid'
            }
        )
        print(f"✓ Test invoice created/found: {self.test_invoice.invoice_number}")
        
        print("\n✓ Test data setup complete!\n")
    
    def verify_email_config(self):
        """Verify Mailtrap configuration"""
        print("="*60)
        print("VERIFYING EMAIL CONFIGURATION")
        print("="*60)
        
        required_settings = [
            'EMAIL_HOST',
            'EMAIL_PORT',
            'EMAIL_HOST_USER',
            'EMAIL_HOST_PASSWORD',
            'DEFAULT_FROM_EMAIL'
        ]
        
        missing = []
        for setting in required_settings:
            if not hasattr(settings, setting):
                missing.append(setting)
            else:
                value = getattr(settings, setting)
                # Mask password
                if 'PASSWORD' in setting:
                    display_value = '*' * len(str(value))
                else:
                    display_value = value
                print(f"✓ {setting}: {display_value}")
        
        if missing:
            print(f"\n✗ Missing settings: {', '.join(missing)}")
            return False
        
        print("\n✓ Email configuration verified!\n")
        return True
    
    def test_connection(self):
        """Test SMTP connection to Mailtrap"""
        print("="*60)
        print("TESTING SMTP CONNECTION")
        print("="*60)
        
        try:
            from django.core.mail import get_connection
            connection = get_connection()
            connection.open()
            connection.close()
            print("✓ Successfully connected to Mailtrap SMTP server!")
            self.results.append(('Connection Test', 'PASSED'))
            return True
        except Exception as e:
            print(f"✗ Connection failed: {str(e)}")
            self.results.append(('Connection Test', f'FAILED: {str(e)}'))
            return False
    
    def test_welcome_email(self):
        """Test welcome email"""
        print("\n" + "="*60)
        print("TEST 1: WELCOME EMAIL")
        print("="*60)
        
        try:
            result = send_welcome_email(self.test_user.id)
            if result['status'] == 'success':
                print(f"✓ Welcome email sent successfully to {self.test_user.email}")
                print(f"  Message: {result['message']}")
                self.results.append(('Welcome Email', 'PASSED'))
            else:
                print(f"✗ Failed: {result['message']}")
                self.results.append(('Welcome Email', f"FAILED: {result['message']}"))
        except Exception as e:
            print(f"✗ Exception: {str(e)}")
            self.results.append(('Welcome Email', f'FAILED: {str(e)}'))
        
        # Wait to avoid rate limiting
        print("  Waiting 15 seconds to avoid rate limit...")
        time.sleep(15)
    
    def test_service_credentials_email(self):
        """Test service credentials email"""
        print("\n" + "="*60)
        print("TEST 2: SERVICE CREDENTIALS EMAIL")
        print("="*60)
        
        try:
            result = send_service_credentials_email(self.test_service.id)
            if result['status'] == 'success':
                print(f"✓ Service credentials email sent successfully")
                print(f"  Service: {self.test_service.plan.name}")
                print(f"  VM ID: {self.test_service.vm_id}")
                print(f"  IP: {self.test_service.ip_address}")
                self.results.append(('Service Credentials Email', 'PASSED'))
            else:
                print(f"✗ Failed: {result['message']}")
                self.results.append(('Service Credentials Email', f"FAILED: {result['message']}"))
        except Exception as e:
            print(f"✗ Exception: {str(e)}")
            self.results.append(('Service Credentials Email', f'FAILED: {str(e)}'))
        
        # Wait to avoid rate limiting
        print("  Waiting 15 seconds to avoid rate limit...")
        time.sleep(15)
    
    def test_vm_deployment_failed_email(self):
        """Test VM deployment failure email"""
        print("\n" + "="*60)
        print("TEST 3: VM DEPLOYMENT FAILED EMAIL")
        print("="*60)
        
        try:
            error_msg = "Test error: Proxmox connection timeout"
            result = send_vm_deployment_failed_email(self.test_service.id, error_msg)
            if result['status'] == 'success':
                print(f"✓ Deployment failure email sent successfully")
                print(f"  Error message: {error_msg}")
                self.results.append(('VM Deployment Failed Email', 'PASSED'))
            else:
                print(f"✗ Failed: {result['message']}")
                self.results.append(('VM Deployment Failed Email', f"FAILED: {result['message']}"))
        except Exception as e:
            print(f"✗ Exception: {str(e)}")
            self.results.append(('VM Deployment Failed Email', f'FAILED: {str(e)}'))
        
        # Wait to avoid rate limiting
        print("  Waiting 15 seconds to avoid rate limit...")
        time.sleep(15)
    
    def test_renewal_reminder_email(self):
        """Test renewal reminder email"""
        print("\n" + "="*60)
        print("TEST 4: RENEWAL REMINDER EMAIL")
        print("="*60)
        
        try:
            result = send_renewal_reminder_email(self.test_service.id, self.test_invoice.id)
            if result['status'] == 'success':
                print(f"✓ Renewal reminder email sent successfully")
                print(f"  Invoice: {self.test_invoice.invoice_number}")
                print(f"  Amount: ${self.test_invoice.amount}")
                print(f"  Due Date: {self.test_invoice.due_date.strftime('%Y-%m-%d')}")
                self.results.append(('Renewal Reminder Email', 'PASSED'))
            else:
                print(f"✗ Failed: {result['message']}")
                self.results.append(('Renewal Reminder Email', f"FAILED: {result['message']}"))
        except Exception as e:
            print(f"✗ Exception: {str(e)}")
            self.results.append(('Renewal Reminder Email', f'FAILED: {str(e)}'))
        
        # Wait to avoid rate limiting
        print("  Waiting 15 seconds to avoid rate limit...")
        time.sleep(15)
    
    def test_suspension_email(self):
        """Test service suspension email"""
        print("\n" + "="*60)
        print("TEST 5: SERVICE SUSPENSION EMAIL")
        print("="*60)
        
        try:
            result = send_suspension_email(self.test_service.id)
            if result['status'] == 'success':
                print(f"✓ Suspension email sent successfully")
                print(f"  Service: {self.test_service.plan.name}")
                self.results.append(('Service Suspension Email', 'PASSED'))
            else:
                print(f"✗ Failed: {result['message']}")
                self.results.append(('Service Suspension Email', f"FAILED: {result['message']}"))
        except Exception as e:
            print(f"✗ Exception: {str(e)}")
            self.results.append(('Service Suspension Email', f'FAILED: {str(e)}'))
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        passed = sum(1 for _, status in self.results if status == 'PASSED')
        total = len(self.results)
        
        for test_name, status in self.results:
            icon = "✓" if status == "PASSED" else "✗"
            print(f"{icon} {test_name}: {status}")
        
        print("\n" + "-"*60)
        print(f"Total: {passed}/{total} tests passed")
        print("-"*60)
        
        if passed == total:
            print("\n🎉 All tests passed! Check your Mailtrap inbox for the emails.")
        else:
            print("\n⚠️  Some tests failed. Check the errors above.")
        
        print("\n" + "="*60)
        print("NEXT STEPS")
        print("="*60)
        print("1. Log into your Mailtrap account at https://mailtrap.io")
        print("2. Go to your inbox")
        print("3. Verify that all 5 emails were received")
        print("4. Check email formatting and content")
        print("5. Test any links or buttons in the emails")
        print("="*60 + "\n")
    
    def cleanup(self):
        """Optional: Clean up test data"""
        print("\n" + "="*60)
        print("CLEANUP (Optional)")
        print("="*60)
        
        response = input("Do you want to delete test data? (yes/no): ").lower()
        
        if response == 'yes':
            if self.test_invoice:
                self.test_invoice.delete()
                print("✓ Deleted test invoice")
            
            if self.test_service:
                self.test_service.delete()
                print("✓ Deleted test service")
            
            if self.test_plan:
                self.test_plan.delete()
                print("✓ Deleted test plan")
            
            if self.test_user:
                self.test_user.delete()
                print("✓ Deleted test user")
            
            print("\n✓ Cleanup complete!")
        else:
            print("\n✓ Test data preserved for future testing")
    
    def run_all_tests(self):
        """Run all email tests"""
        print("\n")
        print("█" * 60)
        print("  HOSTPRO EMAIL TESTING SUITE - MAILTRAP")
        print("█" * 60)
        
        # Verify configuration
        if not self.verify_email_config():
            print("\n✗ Please configure your email settings before testing")
            return
        
        # Test connection
        if not self.test_connection():
            print("\n✗ Cannot proceed without SMTP connection")
            return
        
        # Setup test data
        self.setup()
        
        # Run all email tests
        self.test_welcome_email()
        self.test_service_credentials_email()
        self.test_vm_deployment_failed_email()
        self.test_renewal_reminder_email()
        self.test_suspension_email()
        
        # Print summary
        self.print_summary()
        
        # Optional cleanup
        self.cleanup()


def main():
    """Main entry point"""
    tester = EmailTester()
    try:
        tester.run_all_tests()
    except KeyboardInterrupt:
        print("\n\n✗ Testing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()