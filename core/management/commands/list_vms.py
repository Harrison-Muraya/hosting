from django.core.management.base import BaseCommand
from core.models import Service
from vms.proxmox import ProxmoxManager

class Command(BaseCommand):
    help = 'List all VMs for managed services'

    def handle(self, *args, **options):
        self.stdout.write("="*80)
        self.stdout.write(self.style.SUCCESS('Managed VMs'))
        self.stdout.write("="*80)
        
        services = Service.objects.filter(vm_id__isnull=False).select_related('user', 'plan')
        
        if not services:
            self.stdout.write("No managed VMs found")
            return
        
        proxmox = ProxmoxManager()
        
        self.stdout.write(f"\n{'VMID':<8} {'User':<15} {'Plan':<20} {'Status':<12} {'IP Address':<15}")
        self.stdout.write("-"*80)
        
        for service in services:
            status = proxmox.get_vm_status(service.vm_id) if service.vm_id else 'unknown'
            self.stdout.write(
                f"{service.vm_id or 'N/A':<8} "
                f"{service.user.username:<15} "
                f"{service.plan.name:<20} "
                f"{status:<12} "
                f"{service.ip_address or 'Pending':<15}"
            )
        
        self.stdout.write("\n" + "="*80)
        self.stdout.write(f"Total: {services.count()} VMs")