from django.core.management.base import BaseCommand
from vms.proxmox import ProxmoxManager

class Command(BaseCommand):
    help = 'Delete a VM from Proxmox'

    def add_arguments(self, parser):
        parser.add_argument('vmid', type=int, help='VM ID to delete')
        parser.add_argument('--force', action='store_true', help='Skip confirmation')

    def handle(self, *args, **options):
        vmid = options['vmid']
        
        if not options['force']:
            confirm = input(f"Are you sure you want to delete VM {vmid}? [y/N]: ")
            if confirm.lower() != 'y':
                self.stdout.write("Aborted")
                return
        
        self.stdout.write(f"Deleting VM {vmid}...")
        proxmox = ProxmoxManager()
        
        if proxmox.delete_vm(vmid):
            self.stdout.write(self.style.SUCCESS(f"✅ VM {vmid} deleted successfully"))
        else:
            self.stdout.write(self.style.ERROR(f"❌ Failed to delete VM {vmid}"))