from proxmoxer import ProxmoxAPI
from django.conf import settings
import random
import string

class ProxmoxManager:
    def __init__(self):
        self.host = settings.PROXMOX_HOST
        self.user = settings.PROXMOX_USER
        self.password = settings.PROXMOX_PASSWORD
        self.node = settings.PROXMOX_NODE
        
        if self.host and self.user and self.password:
            self.proxmox = ProxmoxAPI(
                self.host,
                user=self.user,
                password=self.password,
                verify_ssl=False
            )
        else:
            self.proxmox = None
    
    def generate_password(self, length=16):
        chars = string.ascii_letters + string.digits + "!@#$%^&*()"
        return ''.join(random.choice(chars) for _ in range(length))
    
    def create_vm(self, vmid, name, cores, memory, disk):
        if not self.proxmox:
            return {'status': 'error', 'message': 'Proxmox not configured'}
        
        try:
            # Create VM
            self.proxmox.nodes(self.node).qemu.create(
                vmid=vmid,
                name=name,
                cores=cores,
                memory=memory,
                scsihw='virtio-scsi-pci',
                scsi0=f'local-lvm:{disk}',
                net0='virtio,bridge=vmbr0',
                ostype='l26',
                boot='c',
                bootdisk='scsi0'
            )
            
            # Start VM
            self.proxmox.nodes(self.node).qemu(vmid).status.start.post()
            
            # Get IP address (simplified - in production, wait for IP assignment)
            vm_config = self.proxmox.nodes(self.node).qemu(vmid).config.get()
            
            return {
                'status': 'success',
                'vmid': vmid,
                'name': name,
                'ip_address': self.get_vm_ip(vmid)
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def get_vm_ip(self, vmid):
        try:
            interfaces = self.proxmox.nodes(self.node).qemu(vmid).agent.get('network-get-interfaces')
            for interface in interfaces.get('result', []):
                if interface.get('name') == 'eth0':
                    for ip in interface.get('ip-addresses', []):
                        if ip.get('ip-address-type') == 'ipv4':
                            return ip.get('ip-address')
        except:
            pass
        return None
    
    def stop_vm(self, vmid):
        if not self.proxmox:
            return False
        try:
            self.proxmox.nodes(self.node).qemu(vmid).status.stop.post()
            return True
        except:
            return False
    
    def start_vm(self, vmid):
        if not self.proxmox:
            return False
        try:
            self.proxmox.nodes(self.node).qemu(vmid).status.start.post()
            return True
        except:
            return False
    
    def delete_vm(self, vmid):
        if not self.proxmox:
            return False
        try:
            # Stop VM first
            self.stop_vm(vmid)
            # Delete VM
            self.proxmox.nodes(self.node).qemu(vmid).delete()
            return True
        except:
            return False
    
    def get_next_vmid(self):
        if not self.proxmox:
            return random.randint(1000, 9999)
        try:
            return self.proxmox.cluster.nextid.get()
        except:
            return random.randint(1000, 9999)