import subprocess
import re
import platform
import socket
import os
import sys
from contextlib import contextmanager

@contextmanager
def suppress_stderr():
    """A context manager that redirects stderr to devnull."""
    with open(os.devnull, 'w') as devnull:
        old_stderr = sys.stderr
        sys.stderr = devnull
        try:
            yield
        finally:
            sys.stderr = old_stderr

# Suppress scapy's warning about Wireshark's manuf file
with suppress_stderr():
    from scapy.all import ARP, Ether, srp, conf  # pyright: ignore[reportAttributeAccessIssue]
from device_manager import DeviceManager
from config import config

# Nmap module and availability
class NmapState:
    _available = False
    _scanner = None
    
    @classmethod
    def initialize(cls):
        try:
            import nmap
            try:
                # Test if nmap is properly installed and accessible
                cls._scanner = nmap.PortScanner()
                cls._available = True
            except Exception as e:
                print(f"Nmap is installed but not working: {e}")
                cls._available = False
        except ImportError:
            print("Nmap module not installed. Some features will be limited.")
            cls._available = False
    
    @classmethod
    def is_available(cls):
        return cls._available
    
    @classmethod
    def get_scanner(cls):
        return cls._scanner
    
    @classmethod
    def disable(cls):
        cls._available = False
        cls._scanner = None

# Initialize Nmap state
NmapState.initialize()


class WiFiScanner:
    def __init__(self):
        self.device_manager = DeviceManager()

        # Initialize nmap only if available
        if NmapState.is_available():
            self.nm = NmapState.get_scanner()
        else:
            self.nm = None

        # Configure scapy for Windows
        if platform.system() == "Windows":
            conf.use_winpcapy = True  # pyright: ignore[reportAttributeAccessIssue]

        print(f"Scanner initialized for network: {config.NETWORK_RANGE}")
        print(f"Using interface: {config.NETWORK_INTERFACE}")

    def get_windows_arp_table(self):
        """Get ARP table on Windows using arp command"""
        try:
            result = subprocess.run(['arp', '-a'], capture_output=True, text=True, timeout=10)
            devices = []

            for line in result.stdout.split('\n'):
                line = line.strip()
                if not line or not line.startswith(config.NETWORK_RANGE.split('.')[0]):
                    continue

                parts = line.split()
                if len(parts) < 2:
                    continue

                ip = parts[0]
                mac = parts[1]

                # Validate MAC address format
                if not re.match(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$', mac):
                    continue

                mac = mac.replace('-', ':').upper()
                if self._is_valid_device(ip, mac):
                    devices.append({
                        'ip': ip,
                        'mac': mac,
                        'hostname': self.get_hostname(ip)
                    })

            return devices
        except Exception as e:
            print(f"Windows ARP table error: {e}")
            return []

    def _is_valid_device(self, ip, mac):
        """Check if device should be included in results"""
        if mac in ['FF-FF-FF-FF-FF-FF', '00:00:00:00:00:00']:
            return False

        if ip.endswith('.255') or ip.startswith('224.') or ip.startswith('239.'):
            return False

        if ip == config.LOCAL_IP:
            return False

        return True

    def scan_arp(self):
        """Scan network using ARP requests"""
        if platform.system() == "Windows":
            return self.get_windows_arp_table()

        try:
            arp = ARP(pdst=config.NETWORK_RANGE)
            ether = Ether(dst="ff:ff:ff:ff:ff:ff")
            packet = ether / arp

            result = srp(packet, timeout=3, verbose=0, iface=config.NETWORK_INTERFACE)[0]

            devices = []
            for sent, received in result:
                if self._is_valid_device(received.psrc, received.hwsrc):
                    devices.append({
                        'ip': received.psrc,
                        'mac': received.hwsrc,
                        'hostname': self.get_hostname(received.psrc)
                    })

            return devices
        except Exception as e:
            print(f"ARP scan error: {e}")
            return []

    def get_hostname(self, ip):
        """Get hostname"""
        try:
            if platform.system() == "Windows":
                result = subprocess.run(['nslookup', ip], capture_output=True, text=True, timeout=2)
                for line in result.stdout.split('\n'):
                    if 'Name:' in line:
                        hostname = line.split('Name:')[1].strip()
                        if hostname and not hostname.lower().startswith('unknown'):
                            return hostname
            else:
                result = subprocess.check_output(['nslookup', ip], timeout=2, stderr=subprocess.DEVNULL)
                for line in result.decode().split('\n'):
                    if 'name =' in line:
                        return line.split('=')[1].strip()
        except:
            pass

        try:
            return socket.gethostbyaddr(ip)[0]
        except:
            return "Unknown"

    def scan_nmap(self):
        """Scan network using nmap"""
        if not NmapState.is_available() or self.nm is None:
            if not NmapState.is_available():
                print("Nmap scanning is not available. Install python-nmap for better results.")
            return []
            
        try:
            print(f"Scanning with nmap: {config.NETWORK_RANGE}")
            self.nm.scan(hosts=config.NETWORK_RANGE, arguments='-sn')
            
            devices = []
            for host in self.nm.all_hosts():
                if not self.nm[host]:
                    continue
                    
                mac = self.nm[host]['addresses'].get('mac', 'Unknown')
                if mac == 'Unknown':
                    continue
                    
                mac = mac.upper()
                if self._is_valid_device(host, mac):
                    devices.append({
                        'ip': host,
                        'mac': mac,
                        'hostname': self.get_hostname(host)
                    })
                    
            return devices
            
        except Exception as e:
            print(f"Nmap scan error: {e}")
            # Disable Nmap for future scans if it fails
            NmapState.disable()
            self.nm = None
            return []

    def scan_multiple_ranges(self):
        """Try multiple ranges"""
        if not NmapState.is_available():
            return []

        common_ranges = [
            config.NETWORK_RANGE,
            '192.168.0.0/24',
            '192.168.1.0/24',
            '192.168.2.0/24',
            '192.168.3.0/24',
            '10.0.0.0/24',
            '172.16.0.0/24'
        ]

        all_devices = []

        for network_range in common_ranges:
            try:
                print(f"Trying range: {network_range}")
                self.nm.scan(hosts=network_range, arguments='-sn') # pyright: ignore[reportOptionalMemberAccess]

                for host in self.nm.all_hosts(): # pyright: ignore[reportOptionalMemberAccess]
                    if not self.nm[host]: # pyright: ignore[reportOptionalSubscript]
                        continue
                    mac = self.nm[host]['addresses'].get('mac', 'Unknown') # pyright: ignore[reportOptionalSubscript]

                    if self._is_valid_device(host, mac):
                        all_devices.append({
                            'ip': host,
                            'mac': mac,
                            'hostname': self.nm[host].hostname() or "Unknown" # type: ignore
                        })
            except:
                continue

        return all_devices

    def get_connected_devices(self):
        """Get connected devices by running all available scans and merging the results."""
        print("Scanning for connected devices...")
        
        # Run all scans and merge the results
        arp_devices = self.scan_arp()
        print(f"ARP scan found {len(arp_devices)} devices")
        
        nmap_devices = self.scan_nmap()
        print(f"Nmap scan found {len(nmap_devices)} devices")

        # Merge devices, giving preference to nmap results for more detail
        merged_devices = {device['mac']: device for device in arp_devices}
        for device in nmap_devices:
            merged_devices[device['mac']] = device

        # If still no devices, try scanning multiple ranges
        if not merged_devices:
            multi_range_devices = self.scan_multiple_ranges()
            print(f"Multi-range scan found {len(multi_range_devices)} devices")
            for device in multi_range_devices:
                merged_devices[device['mac']] = device

        # Update the device manager with all found devices
        for mac, device in merged_devices.items():
            if mac != 'Unknown':
                self.device_manager.update_device(device)

        # Return all devices from the manager, including offline ones
        final_devices = self.device_manager.get_all_devices()
        print(f"Total known devices: {len(final_devices)}")

        return final_devices
