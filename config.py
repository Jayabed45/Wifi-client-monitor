import json
import os
import platform
import subprocess
import re
from datetime import datetime

class Config:
    def __init__(self):
        self._network_info = self._detect_network_info()
    
    def _detect_network_info(self):
        """Dynamically detect network interface and range"""
        system = platform.system()
        
        if system == "Windows":
            return self._detect_windows_network()
        else:
            return self._detect_linux_network()
    
    def _detect_windows_network(self):
        """Detect network info on Windows"""
        try:
            # Get network interface info using ipconfig
            result = subprocess.run(['ipconfig'], capture_output=True, text=True, timeout=10)
            lines = result.stdout.split('\n')
            
            interface = "Wi-Fi"
            ip_address = None
            subnet_mask = None
            
            for i, line in enumerate(lines):
                if "Wireless LAN adapter Wi-Fi" in line or "Ethernet adapter Ethernet" in line:
                    # Look for IP and subnet mask in following lines
                    for j in range(i, min(i+10, len(lines))):
                        if "IPv4 Address" in lines[j]:
                            ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', lines[j])
                            if ip_match:
                                ip_address = ip_match.group(1)
                        elif "Subnet Mask" in lines[j]:
                            mask_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', lines[j])
                            if mask_match:
                                subnet_mask = mask_match.group(1)
            
            if ip_address and subnet_mask:
                network_range = self._calculate_network_range(ip_address, subnet_mask)
                return {
                    'interface': interface,
                    'network_range': network_range,
                    'local_ip': ip_address,
                    'subnet_mask': subnet_mask
                }
        except Exception as e:
            print(f"Windows network detection error: {e}")
        
        # Fallback to common ranges
        return {
            'interface': 'Wi-Fi',
            'network_range': '192.168.1.0/24',
            'local_ip': 'Unknown',
            'subnet_mask': '255.255.255.0'
        }
    
    def _detect_linux_network(self):
        """Detect network info on Linux"""
        try:
            # Try to get default interface
            result = subprocess.run(['ip', 'route'], capture_output=True, text=True, timeout=5)
            lines = result.stdout.split('\n')
            
            for line in lines:
                if 'default' in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        interface = parts[4]
                        break
            else:
                interface = "wlan0"  # Default fallback
            
            # Get IP and network info for the interface
            result = subprocess.run(['ip', 'addr', 'show', interface], capture_output=True, text=True, timeout=5)
            ip_match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)/(\d+)', result.stdout)
            
            if ip_match:
                ip_address = ip_match.group(1)
                cidr = ip_match.group(2)
                network_range = f"{'.'.join(ip_address.split('.')[:3])}.0/{cidr}"
                
                return {
                    'interface': interface,
                    'network_range': network_range,
                    'local_ip': ip_address,
                    'subnet_mask': self._cidr_to_mask(int(cidr))
                }
        except Exception as e:
            print(f"Linux network detection error: {e}")
        
        # Fallback
        return {
            'interface': 'wlan0',
            'network_range': '192.168.1.0/24',
            'local_ip': 'Unknown',
            'subnet_mask': '255.255.255.0'
        }
    
    def _calculate_network_range(self, ip_address, subnet_mask):
        """Calculate network range from IP and subnet mask"""
        try:
            ip_parts = [int(x) for x in ip_address.split('.')]
            mask_parts = [int(x) for x in subnet_mask.split('.')]
            
            network_parts = []
            for i in range(4):
                network_parts.append(ip_parts[i] & mask_parts[i])
            
            # Count CIDR bits
            cidr = bin(int.from_bytes(mask_parts, 'big')).count('1')
            
            return f"{'.'.join(map(str, network_parts))}/{cidr}"
        except:
            # Fallback calculation
            network_prefix = '.'.join(ip_address.split('.')[:-1])
            return f"{network_prefix}.0/24"
    
    def _cidr_to_mask(self, cidr):
        """Convert CIDR to subnet mask"""
        mask = (0xffffffff >> (32 - cidr)) << (32 - cidr)
        return '.'.join([str((mask >> (24 - i * 8)) & 0xff) for i in range(4)])
    
    @property
    def NETWORK_INTERFACE(self):
        return self._network_info['interface']
    
    @property
    def NETWORK_RANGE(self):
        return self._network_info['network_range']
    
    @property
    def LOCAL_IP(self):
        return self._network_info['local_ip']
    
    # Other configuration settings
    DEFAULT_TIME_LIMIT = 120  # 2 hours default
    DISCONNECT_MESSAGE = "Your WiFi time is up. Please disconnect now."
    BLACKLIST_FILE = "blacklist.json"
    SCAN_INTERVAL = 30
    
    def load_blacklist(self):
        """Load blacklist from file"""
        try:
            if os.path.exists('blacklist.json'):
                with open('blacklist.json', 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading blacklist: {e}")
        return {}
        
    def save_blacklist(self, blacklist):
        """Save blacklist to file"""
        with open('blacklist.json', 'w') as f:
            json.dump(blacklist, f, indent=4)
            
    def block_ip_windows(self, ip_address):
        """Block an IP address using Windows Firewall"""
        try:
            rule_name = f"Block_WiFi_Manager_{ip_address}"
            # Delete existing rule if it exists
            subprocess.run(
                ['netsh', 'advfirewall', 'firewall', 'delete', 'rule', f'name="{rule_name}"'],
                capture_output=True, text=True
            )
            # Add new block rule
            subprocess.run([
                'netsh', 'advfirewall', 'firewall', 'add', 'rule',
                f'name="{rule_name}"',
                'dir=out',
                'action=block',
                f'remoteip={ip_address}',
                'enable=yes',
                'profile=any'
            ], capture_output=True, text=True)
            return True
        except Exception as e:
            print(f"Failed to block IP {ip_address}: {e}")
            return False

    def unblock_ip_windows(self, ip_address):
        """Unblock an IP address in Windows Firewall"""
        try:
            rule_name = f"Block_WiFi_Manager_{ip_address}"
            subprocess.run(
                ['netsh', 'advfirewall', 'firewall', 'delete', 'rule', f'name="{rule_name}"'],
                capture_output=True, text=True
            )
            return True
        except Exception as e:
            print(f"Failed to unblock IP {ip_address}: {e}")
            return False

# Global config instance
config = Config()