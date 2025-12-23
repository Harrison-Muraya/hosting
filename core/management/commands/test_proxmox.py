from django.core.management.base import BaseCommand
from vms.proxmox import ProxmoxManager
from django.conf import settings

class Command(BaseCommand):
    help = 'Test Proxmox connection and display configuration'

    def handle(self, *args, **options):
        self.stdout.write("="*60)
        self.stdout.write(self.style.SUCCESS('Testing Proxmox Configuration'))
        self.stdout.write("="*60)
        
        # Display configuration
        self.stdout.write("\n📋 Configuration:")
        self.stdout.write(f"  Host: {settings.PROXMOX_HOST}")
        self.stdout.write(f"  User: {settings.PROXMOX_USER}")
        self.stdout.write(f"  Node: {settings.PROXMOX_NODE}")
        self.stdout.write(f"  SSL Verify: {getattr(settings, 'PROXMOX_VERIFY_SSL', False)}")
        
        # Test connection
        self.stdout.write("\n🔌 Testing Connection...")
        proxmox = ProxmoxManager()
        result = proxmox.test_connection()
        
        if result['status'] == 'success':
            self.stdout.write(self.style.SUCCESS("\n✅ Connection Successful!"))
            self.stdout.write(f"  Proxmox Version: {result.get('version', 'Unknown')}")
            self.stdout.write(f"  Available Nodes: {', '.join(result.get('nodes', []))}")
            
            # Get storage info
            self.stdout.write("\n💾 Available Storage:")
            storage_list = proxmox.get_storage_list()
            for storage in storage_list:
                self.stdout.write(f"  • {storage}")
            
            # Get next VMID
            next_vmid = proxmox.get_next_vmid()
            self.stdout.write(f"\n🆔 Next Available VM ID: {next_vmid}")
            
        else:
            self.stdout.write(self.style.ERROR(f"\n❌ Connection Failed!"))
            self.stdout.write(self.style.ERROR(f"  Error: {result['message']}"))
            self.stdout.write("\n💡 Troubleshooting:")
            self.stdout.write("  1. Check if Proxmox host is reachable")
            self.stdout.write("  2. Verify credentials in .env file")
            self.stdout.write("  3. Ensure port 8006 is open")
            self.stdout.write("  4. Check if Proxmox is running")
        
        self.stdout.write("\n" + "="*60)