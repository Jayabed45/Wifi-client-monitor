import time
from datetime import datetime, timedelta
from config import config

class DeviceManager:
    def __init__(self):
        self.devices = {}
        self.blacklist = config.load_blacklist()
        self.connection_times = {}
    
    def update_device(self, device_info):
        """Update device information and track connection time"""
        mac = device_info['mac']
        current_time = time.time()
        
        if mac not in self.connection_times:
            self.connection_times[mac] = current_time
        
        self.devices[mac] = {
            **device_info,
            'first_seen': self.connection_times[mac],
            'last_seen': current_time,
            'connection_duration': current_time - self.connection_times[mac],
            'is_blacklisted': mac in self.blacklist
        }
    
    def get_all_devices(self):
        """Get all devices with formatted information and status"""
        formatted_devices = []
        current_time = time.time()
        
        for mac, info in self.devices.items():
            # Determine status based on last_seen timestamp (e.g., active within last 5 minutes)
            status = "ACTIVE" if (current_time - info['last_seen']) < 300 else "OFFLINE"
            
            formatted_devices.append({
                'mac': mac,
                'ip': info['ip'],
                'hostname': info['hostname'],
                'connection_duration': self.format_duration(info['connection_duration']),
                'is_blacklisted': info['is_blacklisted'],
                'first_seen': datetime.fromtimestamp(info['first_seen']).strftime('%Y-%m-%d %H:%M:%S'),
                'status': status
            })
            
        return formatted_devices
    
    def format_duration(self, seconds):
        """Format duration in human-readable format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def blacklist_device(self, mac_address, reason="Manual blacklist"):
        """Add device to blacklist and block its IP"""
        # Get the device's IP before adding to blacklist
        device_ip = None
        for dev_mac, info in self.devices.items():
            if dev_mac == mac_address:
                device_ip = info.get('ip')
                break
        
        self.blacklist[mac_address] = {
            'timestamp': datetime.now().isoformat(),
            'reason': reason,
            'ip': device_ip
        }
        config.save_blacklist(self.blacklist)
        
        # Block the device's IP in Windows Firewall
        if device_ip and platform.system() == "Windows":
            config.block_ip_windows(device_ip)
        
        print(f"Device {mac_address} added to blacklist and blocked")
    
    def remove_from_blacklist(self, mac_address):
        """Remove device from blacklist and unblock its IP"""
        if mac_address in self.blacklist:
            # Get the IP before removing from blacklist
            device_ip = self.blacklist[mac_address].get('ip')
            
            # Remove from blacklist
            del self.blacklist[mac_address]
            config.save_blacklist(self.blacklist)
            
            # Unblock the IP in Windows Firewall
            if device_ip and platform.system() == "Windows":
                config.unblock_ip_windows(device_ip)
            
            print(f"Device {mac_address} removed from blacklist and unblocked")
        else:
            print(f"Device {mac_address} not found in blacklist")
    
    def check_time_limit(self, mac_address, time_limit_minutes=config.DEFAULT_TIME_LIMIT):
        """Check if device has exceeded time limit"""
        if mac_address in self.devices:
            connection_time = self.devices[mac_address]['connection_duration']
            return connection_time > (time_limit_minutes * 60)
        return False