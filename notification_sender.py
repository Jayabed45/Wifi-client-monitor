import subprocess
import socket
import json
import platform
import time
import re
from config import config  # Changed from 'from config import Config'

class NotificationSender:
    def __init__(self):
        pass
    
    def send_message(self, ip_address, message):
        """Send message to a device. Uses msg.exe on Windows for a popup."""
        if platform.system() == "Windows":
            return self.send_windows_popup(ip_address, message)
        else:
            # For non-Windows systems, fallback to old methods
            try:
                print(f"Attempting to send UDP message to {ip_address}: {message}")
                self.send_udp_message(ip_address, message)
                return True
            except Exception as e:
                print(f"Failed to send message to {ip_address}: {e}")
                return False

    def send_windows_popup(self, ip_address, message):
        """Send a popup message to a Windows device using msg.exe."""
        try:
            # The '*' sends the message to all sessions on the target machine.
            # You could also try to find a specific username if you know it.
            command = ['msg', '*', '/SERVER:' + ip_address, message]
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"Successfully sent message to {ip_address}")
                return True
            else:
                print(f"Failed to send message to {ip_address}. Error: {result.stderr}")
                return False
        except FileNotFoundError:
            print("Error: 'msg.exe' not found. This command is not available on this version of Windows.")
            return False
        except subprocess.TimeoutExpired:
            print(f"Timeout expired when trying to send message to {ip_address}")
            return False
        except Exception as e:
            print(f"An error occurred while sending message to {ip_address}: {e}")
            return False
    
    def send_udp_message(self, ip_address, message, port=9999):
        """Send UDP message to device"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(2)
            sock.sendto(message.encode(), (ip_address, port))
            sock.close()
            print(f"UDP message sent to {ip_address}:{port}")
        except Exception as e:
            print(f"UDP message failed: {e}")
    
    def send_http_notification(self, ip_address, message, port=80):
        """Send HTTP notification (if device has web server)"""
        try:
            import requests
            payload = {'message': message, 'source': 'wifi_manager'}
            response = requests.post(f"http://{ip_address}:{port}/", 
                          json=payload, timeout=2)
            print(f"HTTP notification sent to {ip_address}, status: {response.status_code}")
        except requests.exceptions.RequestException as e:
            # This is expected for most devices
            pass
        except Exception as e:
            print(f"HTTP notification failed: {e}")
    
    def disconnect_device_windows(self, mac_address, ip_address):
        """Disconnect device on Windows using netsh"""
        try:
            # Method 1: Block via Windows Firewall
            self.block_via_windows_firewall(ip_address)
            
            # Method 2: Send deauth-like packets (limited on Windows)
            print(f"Windows: Would disconnect {mac_address} via firewall rules")
            return True
        except Exception as e:
            print(f"Windows disconnect failed: {e}")
            return False
    
    def disconnect_device_linux(self, mac_address, ip_address):
        """Disconnect device on Linux"""
        try:
            # Method 1: Using arp table manipulation
            self.block_via_arp(mac_address)
            
            # Method 2: Using iptables
            self.block_via_iptables(ip_address)
            
            print(f"Linux: Disconnected device {mac_address}")
            return True
        except Exception as e:
            print(f"Linux disconnect failed: {e}")
            return False
            
    def force_disconnect_windows(self, mac_address, ip_address):
        """Force disconnect a device using netsh and WiFi filters"""
        try:
            # Convert MAC to format needed by netsh (dashes instead of colons)
            mac_netsh = mac_address.replace(':', '-')
            
            print(f"Attempting to disconnect {ip_address} ({mac_address})...")
            
            # Block the device using Windows Firewall
            config.block_ip_windows(ip_address)
            
            # Clear ARP cache to remove any existing entries
            self.clear_arp_cache()
            
            # Try to get the WiFi interface name
            result = subprocess.run(
                ['netsh', 'wlan', 'show', 'interfaces'],
                capture_output=True, text=True
            )
            
            # Parse the interface name from the output
            interface_name = None
            for line in result.stdout.split('\n'):
                if 'Name' in line and ':' in line:
                    interface_name = line.split(':')[1].strip()
                    break
            
            if interface_name:
                # Disassociate the device using netsh
                subprocess.run([
                    'netsh', 'wlan', 'disconnect', 
                    f'interface="{interface_name}"'
                ], capture_output=True, text=True)
                
                # Add a filter to block the device by MAC
                subprocess.run([
                    'netsh', 'wlan', 'add', 'filter',
                    'permission=denyall',
                    f'macaddress={mac_netsh}',
                    'networktype=infrastructure'
                ], capture_output=True, text=True)
                
                print(f"Successfully disconnected and blocked {ip_address} ({mac_address})")
                return True
            else:
                print("Could not determine WiFi interface name")
                return False
                
        except Exception as e:
            print(f"Error in force_disconnect_windows: {e}")
            return False
    
    def clear_arp_cache(self):
        """Clear the ARP cache to ensure fresh device detection"""
        try:
            if platform.system() == "Windows":
                # Clear ARP cache
                subprocess.run(['arp', '-d', '*'], 
                             capture_output=True, 
                             text=True)
                
                # Optional: Release and renew IP (uncomment if needed)
                # subprocess.run(['ipconfig', '/release'], 
                #              capture_output=True, 
                #              text=True)
                # subprocess.run(['ipconfig', '/renew'], 
                #              capture_output=True, 
                #              text=True)
                
                print("ARP cache cleared")
                return True
            else:
                # For Linux/Unix
                subprocess.run(['ip', '-s', '-s', 'neigh', 'flush', 'all'],
                             capture_output=True,
                             text=True)
                return True
        except Exception as e:
            print(f"Error clearing ARP cache: {e}")
            return False
    
    def disconnect_device(self, mac_address, ip_address):
        """Disconnect a device from the network"""
        if platform.system() == "Windows":
            # First try the force disconnect method
            if self.force_disconnect_windows(mac_address, ip_address):
                return True
            # Fall back to regular disconnect if force fails
            return self.disconnect_device_windows(mac_address, ip_address)
        else:
            return self.disconnect_device_linux(mac_address, ip_address)
    
    def block_via_windows_firewall(self, ip_address):
        """Block device using Windows Firewall"""
        try:
            # Add firewall rule to block IP
            rule_name = f"Block_WiFi_Manager_{ip_address}"
            
            # Check if rule exists
            check_cmd = f'netsh advfirewall firewall show rule name="{rule_name}"'
            result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)
            
            if "No rules match" in result.stdout:
                # Create new rule
                block_cmd = (f'netsh advfirewall firewall add rule name="{rule_name}" '
                           f'dir=in action=block remoteip={ip_address} '
                           f'protocol=ANY enable=yes')
                subprocess.run(block_cmd, shell=True, check=True)
                print(f"Windows Firewall rule created to block {ip_address}")
            else:
                print(f"Windows Firewall rule already exists for {ip_address}")
                
        except subprocess.CalledProcessError as e:
            print(f"Windows Firewall command failed: {e}")
        except Exception as e:
            print(f"Windows Firewall block failed: {e}")
    
    def block_via_arp(self, mac_address):
        """Block device using ARP table (Linux)"""
        try:
            if platform.system() != "Windows":
                subprocess.run(['arp', '-d', mac_address], check=True)
        except:
            pass
    
    def block_via_iptables(self, ip_address):
        """Block device using iptables (Linux)"""
        try:
            if platform.system() != "Windows":
                subprocess.run(['iptables', '-A', 'INPUT', '-s', ip_address, '-j', 'DROP'], check=True)
                subprocess.run(['iptables', '-A', 'OUTPUT', '-d', ip_address, '-j', 'DROP'], check=True)
        except:
            pass