from django.core.management.base import BaseCommand
from vms.proxmox import ProxmoxManager
import time

class Command(BaseCommand):
    help = 'Create a test VM on Proxmox'

    def add_arguments(self, parser):
        parser.add_argument('--name', type=str, default='test-vm', help='VM name')
        parser.add_argument('--cores', type=int, default=1, help='CPU cores')
        parser.add_argument('--memory', type=int, default=1024, help='RAM in MB')
        parser.add_argument('--disk', type=int, default=10, help='Disk size in GB')
        parser.add_argument('--delete', action='store_true', help='Delete VM after creation')

    def handle(self, *args, **options):
        self.stdout.write("="*60)
        self.stdout.write(self.style.SUCCESS('Creating Test VM'))
        self.stdout.write("="*60)
        
        proxmox = ProxmoxManager()
        
        # Test connection
        connection = proxmox.test_connection()
        if connection['status'] != 'success':
            self.stdout.write(self.style.ERROR(f"❌ Connection failed: {connection['message']}"))
            return
        
        # Get VM ID
        vmid = proxmox.get_next_vmid()
        name = options['name']
        cores = options['cores']
        memory = options['memory']
        disk = options['disk']
        
        self.stdout.write(f"\n📋 VM Configuration:")
        self.stdout.write(f"  VM ID: {vmid}")
        self.stdout.write(f"  Name: {name}")
        self.stdout.write(f"  CPU Cores: {cores}")
        self.stdout.write(f"  RAM: {memory}MB")
        self.stdout.write(f"  Disk: {disk}GB")
        
        # Create VM
        self.stdout.write(f"\n🚀 Creating VM...")
        result = proxmox.create_vm(
            vmid=vmid,
            name=name,
            cores=cores,
            memory=memory,
            disk=disk
        )
        
        if result['status'] == 'success':
            self.stdout.write(self.style.SUCCESS(f"\n✅ VM Created Successfully!"))
            self.stdout.write(f"  VM ID: {vmid}")
            self.stdout.write(f"  IP Address: {result.get('ip_address', 'Pending...')}")
            
            # Get VM status
            time.sleep(2)
            status = proxmox.get_vm_status(vmid)
            self.stdout.write(f"  Status: {status}")
            
            # Delete if requested
            if options['delete']:
                self.stdout.write(f"\n🗑️  Deleting test VM...")
                if proxmox.delete_vm(vmid):
                    self.stdout.write(self.style.SUCCESS("  VM deleted successfully"))
                else:
                    self.stdout.write(self.style.ERROR("  Failed to delete VM"))
            else:
                self.stdout.write(f"\n💡 To delete this VM later, run:")
                self.stdout.write(f"  python manage.py delete_vm {vmid}")
        else:
            self.stdout.write(self.style.ERROR(f"\n❌ VM Creation Failed!"))
            self.stdout.write(self.style.ERROR(f"  Error: {result['message']}"))
        
        self.stdout.write("\n" + "="*60)
