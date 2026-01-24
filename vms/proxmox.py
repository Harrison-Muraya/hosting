from proxmoxer import ProxmoxAPI
from django.conf import settings
import random
import string
import time
import logging

logger = logging.getLogger(__name__)

class ProxmoxManager:
    def __init__(self):
        self.host = settings.PROXMOX_HOST
        self.user = settings.PROXMOX_USER
        self.password = settings.PROXMOX_PASSWORD
        self.node = settings.PROXMOX_NODE
        self.verify_ssl = getattr(settings, 'PROXMOX_VERIFY_SSL', False)
        timeout = getattr(settings, 'PROXMOX_TIMEOUT', 60)
        
        # Initialize Proxmox connection
        if self.host and self.user and self.password:
            try:
                self.proxmox = ProxmoxAPI(
                    self.host,
                    user=self.user,
                    password=self.password,
                    verify_ssl=self.verify_ssl,
                    timeout=timeout
                )
                logger.info(f"Connected to Proxmox at {self.host}")
            except Exception as e:
                logger.error(f"Failed to connect to Proxmox: {str(e)}")
                self.proxmox = None
        else:
            logger.warning("Proxmox credentials not configured")
            self.proxmox = None
    
    def test_connection(self):
        """Test Proxmox connection"""
        if not self.proxmox:
            return {'status': 'error', 'message': 'Proxmox not configured'}
        
        try:
            version = self.proxmox.version.get()
            nodes = self.proxmox.nodes.get()
            return {
                'status': 'success',
                'version': version.get('version'),
                'nodes': [node['node'] for node in nodes],
                'message': 'Connected successfully'
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def generate_password(self, length=16):
        """Generate secure random password"""
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(random.choice(chars) for _ in range(length))
    
    def get_next_vmid(self):
        """Get next available VM ID"""
        if not self.proxmox:
            return random.randint(1000, 9999)
        
        try:
            return self.proxmox.cluster.nextid.get()
        except Exception as e:
            logger.error(f"Failed to get next VMID: {str(e)}")
            # Fallback to random ID
            return random.randint(1000, 9999)
    
    def get_storage_list(self):
        """Get available storage on node"""
        if not self.proxmox:
            return ['local-lvm']
        
        try:
            storage = self.proxmox.nodes(self.node).storage.get()
            return [s['storage'] for s in storage if s['type'] in ['dir', 'lvm', 'lvmthin', 'zfs']]
        except Exception as e:
            logger.error(f"Failed to get storage list: {str(e)}")
            return ['local-lvm']

    def wait_for_task(self, upid, timeout=300):
        """
        Wait for a Proxmox task to complete
        """
        logger.info(f"Waiting for task {upid} to complete...")
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            try:
                status = self.proxmox.nodes(self.node).tasks(upid).status.get()
                task_status = status.get('status')
                
                if task_status == 'stopped':
                    exitstatus = status.get('exitstatus')
                    if exitstatus == 'OK':
                        logger.info(f"Task {upid} completed successfully")
                        return True
                    else:
                        logger.error(f"Task {upid} failed: {exitstatus}")
                        return False
            except Exception as e:
                logger.debug(f"Error checking task status: {str(e)}")
            
            time.sleep(2)
        
        logger.warning(f"Task {upid} timed out after {timeout} seconds")
        return False

    def wait_for_lock_release(self, vmid, timeout=60):
        """
        Wait for VM lock to be released
        """
        logger.info(f"Waiting for VM {vmid} lock to be released...")
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            try:
                config = self.proxmox.nodes(self.node).qemu(vmid).config.get()
                # If we can read config without error and there's no lock, we're good
                if 'lock' not in config:
                    logger.info(f"VM {vmid} lock released")
                    return True
            except Exception as e:
                logger.debug(f"Waiting for lock release: {str(e)}")
            
            time.sleep(2)
        
        logger.warning(f"VM {vmid} lock not released after {timeout} seconds")
        return False
    
    def get_vm_disk_size(self, vmid, disk='scsi0'):
        """Get current disk size in GB"""
        try:
            config = self.proxmox.nodes(self.node).qemu(vmid).config.get()
            disk_info = config.get(disk, '')
            # Parse size from string like 'local-lvm:vm-103-disk-0,size=32G'
            if 'size=' in disk_info:
                size_str = disk_info.split('size=')[1].split(',')[0].split(')')[0]
                if 'G' in size_str:
                    return int(size_str.replace('G', ''))
                elif 'M' in size_str:
                    return int(size_str.replace('M', '')) / 1024
            return 0
        except Exception as e:
            logger.error(f"Failed to get disk size: {str(e)}")
            return 0
        
    def wait_for_task(self, upid, timeout=300):
        """
        Wait for a Proxmox task to complete
        """
        logger.info(f"Waiting for task {upid} to complete...")
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            try:
                status = self.proxmox.nodes(self.node).tasks(upid).status.get()
                task_status = status.get('status')
                
                if task_status == 'stopped':
                    exitstatus = status.get('exitstatus')
                    if exitstatus == 'OK':
                        logger.info(f"Task {upid} completed successfully")
                        return True
                    else:
                        logger.error(f"Task {upid} failed: {exitstatus}")
                        return False
            except Exception as e:
                logger.debug(f"Error checking task status: {str(e)}")
            
            time.sleep(2)
        
        logger.warning(f"Task {upid} timed out after {timeout} seconds")
        return False

    def wait_for_lock_release(self, vmid, timeout=60):
        """
        Wait for VM lock to be released
        """
        logger.info(f"Waiting for VM {vmid} lock to be released...")
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            try:
                config = self.proxmox.nodes(self.node).qemu(vmid).config.get()
                # If we can read config without error and there's no lock, we're good
                if 'lock' not in config:
                    logger.info(f"VM {vmid} lock released")
                    return True
            except Exception as e:
                logger.debug(f"Waiting for lock release: {str(e)}")
            
            time.sleep(2)
        
        logger.warning(f"VM {vmid} lock not released after {timeout} seconds")
        return False

    def create_vm_from_template(self, vmid, name, cores, memory, disk, template_id=None, password=None):
        """
        Create VM by cloning a template
        This is faster than creating from scratch
        """
        if not self.proxmox:
            return {
                'status': 'error',
                'message': 'Proxmox not configured'
            }
        
        try:
            # If template_id provided, clone it
            if template_id:
                logger.info(f"Cloning template {template_id} to VM {vmid}")
                
                # Clone the template - this returns a task ID (UPID)
                clone_response = self.proxmox.nodes(self.node).qemu(template_id).clone.post(
                    newid=vmid,
                    name=name,
                    full=1  # Full clone
                )
                
                # Extract UPID from response
                upid = clone_response
                logger.info(f"Clone task started: {upid}")
                
                # Wait for clone task to complete
                if not self.wait_for_task(upid, timeout=300):
                    return {
                        'status': 'error',
                        'message': 'Clone operation timed out or failed'
                    }
                
                # Wait for lock to be released
                if not self.wait_for_lock_release(vmid, timeout=60):
                    logger.warning(f"VM {vmid} lock still present, attempting to continue...")
                
                # Additional wait to ensure everything is settled
                time.sleep(5)
                
                # Resize disk if needed
                logger.info(f"Resizing disk to {disk}GB")
                try:
                    resize_response = self.proxmox.nodes(self.node).qemu(vmid).resize.put(
                        disk='scsi0',
                        size=f'{disk}G'
                    )
                    # Wait for resize to complete
                    if isinstance(resize_response, str) and resize_response.startswith('UPID:'):
                        self.wait_for_task(resize_response, timeout=120)
                    time.sleep(3)
                except Exception as e:
                    logger.warning(f"Disk resize may have failed: {str(e)}")
                
                # Wait for lock again before config update
                self.wait_for_lock_release(vmid, timeout=60)
                
                # Update CPU and memory
                logger.info(f"Updating CPU ({cores} cores) and memory ({memory}MB)")
                try:
                    config_updates = {
                        'cores': cores,
                        'memory': memory
                    }
                    
                    # Add cloud-init configuration if password provided
                    if password:
                        logger.info(f"Configuring cloud-init with new password")
                        # Set cloud-init user and password
                        config_updates['ciuser'] = 'root'
                        config_updates['cipassword'] = password
                        # Enable DHCP for networking
                        config_updates['ipconfig0'] = 'ip=dhcp'
                    
                    self.proxmox.nodes(self.node).qemu(vmid).config.put(**config_updates)
                    time.sleep(3)
                except Exception as e:
                    logger.warning(f"Config update may have failed: {str(e)}")
                
            else:
                # Create new VM from scratch
                logger.info(f"Creating new VM {vmid} from scratch")
                return self.create_vm_from_scratch(vmid, name, cores, memory, disk)
            
            # Wait for lock release before starting
            self.wait_for_lock_release(vmid, timeout=60)
            
            # Start the VM
            logger.info(f"Starting VM {vmid}")
            start_response = self.proxmox.nodes(self.node).qemu(vmid).status.start.post()
            
            # Wait for start task if UPID returned
            if isinstance(start_response, str) and start_response.startswith('UPID:'):
                self.wait_for_task(start_response, timeout=120)
            
            time.sleep(5)
            
            # Wait for IP address
            ip_address = self.wait_for_ip(vmid, timeout=120)
            
            return {
                'status': 'success',
                'vmid': vmid,
                'name': name,
                'ip_address': ip_address,
                'message': 'VM created and started successfully'
            }
            
        except Exception as e:
            logger.error(f"Failed to create VM from template: {str(e)}")
            
            # Try to clean up if VM was partially created
            try:
                logger.info(f"Attempting to clean up VM {vmid}")
                self.delete_vm(vmid)
            except:
                pass
            
            return {
                'status': 'error',
                'message': str(e)
            }

   
    def create_vm_from_scratch(self, vmid, name, cores, memory, disk):
        """
        Create VM from scratch with Ubuntu Cloud Image
        """
        if not self.proxmox:
            return {
                'status': 'error',
                'message': 'Proxmox not configured'
            }
        
        try:
            storage = self.get_storage_list()[0]
            
            logger.info(f"Creating VM {vmid} from scratch")
            
            # Create VM
            self.proxmox.nodes(self.node).qemu.create(
                vmid=vmid,
                name=name,
                cores=cores,
                memory=memory,
                # Network
                net0='virtio,bridge=vmbr0',
                # Boot
                boot='c',
                bootdisk='scsi0',
                # SCSI Controller
                scsihw='virtio-scsi-pci',
                # Disk
                scsi0=f'{storage}:{disk}',
                # OS Type
                ostype='l26',
                # Enable QEMU agent
                agent='enabled=1'
            )
            
            logger.info(f"VM {vmid} created successfully")
            
            # Start VM
            self.proxmox.nodes(self.node).qemu(vmid).status.start.post()
            logger.info(f"VM {vmid} started")
            
            # Wait for IP
            ip_address = self.wait_for_ip(vmid, timeout=120)
            
            return {
                'status': 'success',
                'vmid': vmid,
                'name': name,
                'ip_address': ip_address,
                'message': 'VM created successfully'
            }
            
        except Exception as e:
            logger.error(f"Failed to create VM: {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'vmid': vmid
            }
    # main method to create VM
    # def create_vm(self, vmid, name, cores, memory, disk, template_id=None):
    #     """
    #     Main method to create VM
    #     Tries template first, falls back to scratch
    #     """
    #     logger.info(f"Creating VM: {name} (VMID: {vmid})")
    #     logger.info(f"Resources: {cores} cores, {memory}MB RAM, {disk}GB disk")
        
    #     # Try template first if available
    #     if template_id:
    #         result = self.create_vm_from_template(vmid, name, cores, memory, disk, template_id)
    #     else:
    #         result = self.create_vm_from_scratch(vmid, name, cores, memory, disk)
        
    #     return result

    def create_vm(self, vmid, name, cores, memory, disk, template_id=None, password=None):
        """
        Main method to create VM
        Tries template first, falls back to scratch
        """
        logger.info(f"Creating VM: {name} (VMID: {vmid})")
        logger.info(f"Resources: {cores} cores, {memory}MB RAM, {disk}GB disk")
        
        # Try template first if available
        if template_id:
            result = self.create_vm_from_template(vmid, name, cores, memory, disk, template_id, password)
        else:
            result = self.create_vm_from_scratch(vmid, name, cores, memory, disk)
        
        return result
    
    def wait_for_ip(self, vmid, timeout=480):
        """
        Wait for VM to get an IP address
        """
        logger.info(f"Waiting for VM {vmid} to get IP address...")
        
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            ip = self.get_vm_ip(vmid)
            if ip:
                logger.info(f"VM {vmid} got IP: {ip}")
                return ip
            time.sleep(5)
        
        logger.warning(f"VM {vmid} did not get IP within {timeout} seconds")
        return None
    
    def get_vm_ip(self, vmid):
        """Get VM IP address"""
        if not self.proxmox:
            return None
        
        try:
            # Try to get IP from QEMU agent
            interfaces = self.proxmox.nodes(self.node).qemu(vmid).agent.get('network-get-interfaces')
            
            for interface in interfaces.get('result', []):
                if interface.get('name') in ['eth0', 'ens18', 'ens3']:
                    for ip_info in interface.get('ip-addresses', []):
                        if ip_info.get('ip-address-type') == 'ipv4':
                            ip = ip_info.get('ip-address')
                            if ip and not ip.startswith('127.'):
                                return ip
        except Exception as e:
            logger.debug(f"Could not get IP via agent: {str(e)}")
        
        # Fallback: Try to get IP from ARP/DHCP
        try:
            config = self.proxmox.nodes(self.node).qemu(vmid).config.get()
            # This is a simplified approach - in production you might query your DHCP server
            return None
        except Exception as e:
            logger.debug(f"Could not get IP via config: {str(e)}")
        
        return None
    
    def get_vm_status(self, vmid):
        """Get VM status"""
        if not self.proxmox:
            return 'unknown'
        
        try:
            status = self.proxmox.nodes(self.node).qemu(vmid).status.current.get()
            return status.get('status', 'unknown')
        except Exception as e:
            logger.error(f"Failed to get VM status: {str(e)}")
            return 'error'
    
    def start_vm(self, vmid):
        """Start VM"""
        if not self.proxmox:
            return False
        
        try:
            self.proxmox.nodes(self.node).qemu(vmid).status.start.post()
            logger.info(f"VM {vmid} started")
            return True
        except Exception as e:
            logger.error(f"Failed to start VM {vmid}: {str(e)}")
            return False
    
    def stop_vm(self, vmid):
        """Stop VM"""
        if not self.proxmox:
            return False
        
        try:
            self.proxmox.nodes(self.node).qemu(vmid).status.stop.post()
            logger.info(f"VM {vmid} stopped")
            return True
        except Exception as e:
            logger.error(f"Failed to stop VM {vmid}: {str(e)}")
            return False
    
    def delete_vm(self, vmid):
        """Delete VM"""
        if not self.proxmox:
            return False
        
        try:
            # Stop VM first
            self.stop_vm(vmid)
            time.sleep(2)
            
            # Delete VM
            self.proxmox.nodes(self.node).qemu(vmid).delete()
            logger.info(f"VM {vmid} deleted")
            return True
        except Exception as e:
            logger.error(f"Failed to delete VM {vmid}: {str(e)}")
            return False
    
    def get_vm_info(self, vmid):
        """Get detailed VM information"""
        if not self.proxmox:
            return None
        
        try:
            config = self.proxmox.nodes(self.node).qemu(vmid).config.get()
            status = self.proxmox.nodes(self.node).qemu(vmid).status.current.get()
            
            return {
                'vmid': vmid,
                'name': config.get('name'),
                'cores': config.get('cores'),
                'memory': config.get('memory'),
                'status': status.get('status'),
                'uptime': status.get('uptime'),
                'cpu': status.get('cpu'),
                'mem': status.get('mem'),
                'maxmem': status.get('maxmem'),
                'disk': status.get('disk'),
                'maxdisk': status.get('maxdisk'),
            }
        except Exception as e:
            logger.error(f"Failed to get VM info: {str(e)}")
            return None