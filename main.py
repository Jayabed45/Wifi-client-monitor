import time
import json
import os
import platform
from colorama import Fore, Style, init
from wifi_scanner import WiFiScanner
from device_manager import DeviceManager
from notification_sender import NotificationSender
from config import config

# Initialize colorama for colored output
init(autoreset=True)

class WiFiManager:
    def __init__(self):
        self.scanner = WiFiScanner()
        self.device_manager = DeviceManager()
        self.notification_sender = NotificationSender()
        self.running = False
    
    def check_admin_privileges(self):
        """Check if running with admin privileges"""
        try:
            if platform.system() == "Windows":
                import ctypes
                return ctypes.windll.shell32.IsUserAnAdmin()
            else:
                return os.geteuid() == 0 # type: ignore
        except:
            return False
    
    def display_network_info(self):
        """Display detected network information"""
        print(f"\n{Fore.CYAN}{'Detected Network Configuration':^50}")
        print(f"{Fore.CYAN}{'='*50}")
        print(f"{Fore.YELLOW}Interface:{Fore.WHITE} {config.NETWORK_INTERFACE}")
        print(f"{Fore.YELLOW}Network Range:{Fore.WHITE} {config.NETWORK_RANGE}")
        print(f"{Fore.YELLOW}Local IP:{Fore.WHITE} {config.LOCAL_IP}")
        print(f"{Fore.CYAN}{'-'*50}")
    
    def display_devices(self, devices):
        """Display connected devices in a formatted table"""
        if not devices:
            print(f"{Fore.YELLOW}No devices found on the network.")
            return
            
        print(f"\n{Fore.CYAN}{'Connected Devices':^80}")
        print(f"{Fore.CYAN}{'='*80}")
        print(f"{Fore.YELLOW}{'#':<3} {'Hostname':<20} {'IP Address':<15} {'MAC Address':<17} {'Duration':<12} {'Status':<10}")
        print(f"{Fore.CYAN}{'-'*80}")
        
        for i, device in enumerate(devices, 1):
            if device['is_blacklisted']:
                status_color = Fore.RED
                status_text = "BLOCKED"
            elif device['status'] == 'ACTIVE':
                status_color = Fore.GREEN
                status_text = "ACTIVE"
            else:
                status_color = Fore.YELLOW
                status_text = "OFFLINE"

            print(f"{Fore.WHITE}{i:<3} {device['hostname'][:19]:<20} {device['ip']:<15} {device['mac']:<17} "
                  f"{device['connection_duration']:<12} {status_color}{status_text:<10}")
    
    def show_menu(self):
        """Display main menu"""
        print(f"\n{Fore.GREEN}{'WiFi Manager - Windows Edition':^50}")
        print(f"{Fore.GREEN}{'='*50}")
        print(f"{Fore.YELLOW}1. Scan connected devices")
        print(f"{Fore.YELLOW}2. Blacklist device")
        print(f"{Fore.YELLOW}3. Remove from blacklist")
        print(f"{Fore.YELLOW}4. Send message to device")
        print(f"{Fore.YELLOW}5. Disconnect device (Admin required)")
        print(f"{Fore.YELLOW}6. Auto monitor mode")
        print(f"{Fore.YELLOW}7. View blacklist")
        print(f"{Fore.YELLOW}8. Network Info")
        print(f"{Fore.YELLOW}9. Exit")
        print(f"{Fore.GREEN}{'-'*50}")
        
        # Show admin status
        if self.check_admin_privileges():
            print(f"{Fore.GREEN}✓ Running with Administrator privileges")
        else:
            print(f"{Fore.YELLOW}⚠ Some features require Administrator privileges")
    
    def blacklist_device_interactive(self):
        """Interactive blacklist device"""
        devices = self.scanner.get_connected_devices()
        if not devices:
            print(f"{Fore.RED}No devices found!")
            return
        
        self.display_devices(devices)
        
        try:
            choice = int(input(f"\n{Fore.YELLOW}Enter device number to blacklist (0 to cancel): "))
            if choice == 0:
                return
            
            if 1 <= choice <= len(devices):
                device = devices[choice-1]
                reason = input(f"{Fore.YELLOW}Enter reason for blacklisting: ")
                self.device_manager.blacklist_device(device['mac'], reason)
                print(f"{Fore.RED}Device {device['mac']} has been blacklisted!")
            else:
                print(f"{Fore.RED}Invalid choice!")
        except ValueError:
            print(f"{Fore.RED}Please enter a valid number!")
    
    def send_message_interactive(self):
        """Interactive message sending"""
        devices = self.scanner.get_connected_devices()
        if not devices:
            print(f"{Fore.RED}No devices found!")
            return
        
        self.display_devices(devices)
        
        try:
            choice = int(input(f"\n{Fore.YELLOW}Enter device number to message (0 to cancel): "))
            if choice == 0:
                return
            
            if 1 <= choice <= len(devices):
                device = devices[choice-1]
                message = input(f"{Fore.YELLOW}Enter message to send: ")
                if not message:
                    message = config.DISCONNECT_MESSAGE
                    
                success = self.notification_sender.send_message(device['ip'], message)
                
                if success:
                    print(f"{Fore.GREEN}Message sent to {device['ip']}!")
                else:
                    print(f"{Fore.RED}Failed to send message to {device['ip']}")
            else:
                print(f"{Fore.RED}Invalid choice!")
        except ValueError:
            print(f"{Fore.RED}Please enter a valid number!")
    
    def disconnect_device_interactive(self):
        """Interactive device disconnection"""
        if not self.check_admin_privileges():
            print(f"{Fore.RED}Administrator privileges required for disconnection!")
            return
        
        devices = self.scanner.get_connected_devices()
        if not devices:
            print(f"{Fore.RED}No devices found!")
            return
        
        self.display_devices(devices)
        
        try:
            choice = int(input(f"\n{Fore.YELLOW}Enter device number to disconnect (0 to cancel): "))
            if choice == 0:
                return
            
            if 1 <= choice <= len(devices):
                device = devices[choice-1]
                success = self.notification_sender.disconnect_device(device['mac'], device['ip'])
                
                if success:
                    print(f"{Fore.GREEN}Disconnected {device['ip']}!")
                else:
                    print(f"{Fore.RED}Failed to disconnect {device['ip']}")
            else:
                print(f"{Fore.RED}Invalid choice!")
        except ValueError:
            print(f"{Fore.RED}Please enter a valid number!")
    
    def show_network_info(self):
        """Show detailed network information"""
        self.display_network_info()
        
        # Show additional network details
        try:
            import socket
            hostname = socket.gethostname()
            
            print(f"\n{Fore.CYAN}{'System Information':^50}")
            print(f"{Fore.CYAN}{'='*50}")
            print(f"{Fore.YELLOW}Computer Name:{Fore.WHITE} {hostname}")
            print(f"{Fore.YELLOW}OS Platform:{Fore.WHITE} {platform.system()} {platform.release()}")
            print(f"{Fore.YELLOW}Admin Rights:{Fore.WHITE} {'Yes' if self.check_admin_privileges() else 'No'}")
            
        except Exception as e:
            print(f"{Fore.RED}Error getting system info: {e}")
    
    def auto_monitor_mode(self):
        """Run in auto-monitor mode to enforce blacklist"""
        print(f"\n{Fore.CYAN}Starting auto-monitor mode. Press Ctrl+C to stop...")
        print(f"{Fore.YELLOW}Blacklisted devices will be automatically blocked.")
        
        try:
            while True:
                # Clear screen for better visibility
                os.system('cls' if os.name == 'nt' else 'clear')
                
                # Get and display devices
                print(f"{Fore.CYAN}Scanning network...")
                devices = self.scanner.get_connected_devices()
                self.display_devices(devices)
                
                # Check for blacklisted devices and block them
                blocked_count = 0
                for device in devices:
                    if device['is_blacklisted'] and device['status'] == 'ACTIVE':
                        print(f"{Fore.RED}Blocking blacklisted device: {device['ip']} ({device['mac']})")
                        if platform.system() == "Windows":
                            # Ensure the IP is blocked in Windows Firewall
                            config.block_ip_windows(device['ip'])
                            blocked_count += 1
                        
                        # Optional: Send disconnect message
                        try:
                            self.notification_sender.send_message(
                                device['ip'], 
                                "Your device has been blocked by the network administrator."
                            )
                        except Exception as e:
                            print(f"{Fore.YELLOW}Could not send notification to {device['ip']}: {e}")
                        if self.check_admin_privileges():
                            print(f"{Fore.RED}Disconnecting {device['ip']} in 5 seconds...")
                            time.sleep(5)
                            self.notification_sender.disconnect_device(device['mac'], device['ip'])
                        else:
                            print(f"{Fore.YELLOW}Admin rights needed to disconnect automatically")
                
                print(f"{Fore.CYAN}Waiting {config.SCAN_INTERVAL} seconds until next scan...")
                time.sleep(config.SCAN_INTERVAL)
                
        except KeyboardInterrupt:
            print(f"{Fore.YELLOW}Auto monitor mode stopped")
    
    def view_blacklist(self):
        """Display blacklisted devices"""
        blacklist = config.load_blacklist()
        
        if not blacklist:
            print(f"{Fore.YELLOW}No devices in blacklist")
            return
        
        print(f"\n{Fore.RED}{'Blacklisted Devices':^80}")
        print(f"{Fore.RED}{'='*80}")
        print(f"{Fore.YELLOW}{'MAC Address':<20} {'Reason':<30} {'Date':<20}")
        print(f"{Fore.RED}{'-'*80}")
        
        for mac, info in blacklist.items():
            timestamp = info.get('timestamp', 'N/A')
            if timestamp != 'N/A':
                timestamp = timestamp[:19]  # Show only date and time
            print(f"{Fore.WHITE}{mac:<20} {info.get('reason', 'N/A'):<30} {timestamp:<20}")
    
    def run(self):
        """Main application loop"""
        self.running = True
        
        print(f"{Fore.GREEN}WiFi Manager - Dynamic Network Detection")
        print(f"{Fore.YELLOW}Detected OS: {platform.system()}")
        self.display_network_info()
        
        while self.running:
            self.show_menu()
            
            try:
                choice = input(f"\n{Fore.YELLOW}Enter your choice (1-9): ").strip()
                
                if not choice:
                    continue
                    
                choice = int(choice)
                
                if choice == 1:
                    print(f"{Fore.CYAN}Scanning for all known devices...")
                    devices = self.scanner.get_connected_devices()
                    self.display_devices(devices)
                    
                elif choice == 2:
                    self.blacklist_device_interactive()
                    
                elif choice == 3:
                    mac = input(f"{Fore.YELLOW}Enter MAC address to remove from blacklist: ").strip()
                    if mac:
                        self.device_manager.remove_from_blacklist(mac)
                    else:
                        print(f"{Fore.RED}No MAC address entered!")
                    
                elif choice == 4:
                    self.send_message_interactive()
                    
                elif choice == 5:
                    self.disconnect_device_interactive()
                    
                elif choice == 6:
                    self.auto_monitor_mode()
                    
                elif choice == 7:
                    self.view_blacklist()
                    
                elif choice == 8:
                    self.show_network_info()
                    
                elif choice == 9:
                    self.running = False
                    print(f"{Fore.GREEN}Goodbye!")
                    
                else:
                    print(f"{Fore.RED}Invalid choice! Please try again.")
                    
            except ValueError:
                print(f"{Fore.RED}Please enter a valid number!")
            except KeyboardInterrupt:
                self.running = False
                print(f"\n{Fore.GREEN}Goodbye!")
            except Exception as e:
                print(f"{Fore.RED}An error occurred: {e}")

if __name__ == "__main__":
    manager = WiFiManager()
    
    try:
        manager.run()
    except Exception as e:
        print(f"{Fore.RED}Fatal error: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")