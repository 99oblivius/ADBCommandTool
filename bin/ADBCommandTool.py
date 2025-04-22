import os
import json
import msvcrt
import time
import subprocess
from datetime import datetime
from typing import Callable, List, Optional, Dict, Tuple, Any, Union, Set
from functools import partial

ESCAPE: bytes = b'\x1b'
BACKSPACE: bytes = b'\x08'
TERM_STYLES: Dict[str, str] = {
    'RESET': '\033[0m',
    'BOLD': '\033[1m',
    'GREEN': '\033[92m',
    'RED': '\033[91m',
    'YELLOW': '\033[93m',
    'WHITE': '\033[97m'
}

os.system('')

class Menu:
    def __init__(
        self,
        items: List[str],
        title: str = "Select an option",
        on_select: Optional[Callable[[int], None]] = None,
        on_delete: Optional[Callable[[int], None]] = None,
        on_quit: Optional[Callable[[], None]] = None,
        non_deletable_indices: List[int] = []
    ) -> None:
        self.items: List[str] = items
        self.title: str = title
        self.on_select: Optional[Callable[[int], None]] = on_select
        self.on_delete: Optional[Callable[[int], None]] = on_delete
        self.on_quit: Optional[Callable[[], None]] = on_quit
        self.current: int = 0
        self.last_command_output: str = ""
        self.pending_delete: Optional[int] = None
        self.running: bool = True
        self.non_deletable_indices: List[int] = non_deletable_indices or []
        
        self.key_handlers: Dict[bytes, Callable[[], None]] = {
            b'\xe0': self._handle_extended_key,
            b'w': lambda: self._move_cursor(-1),
            b'W': lambda: self._move_cursor(-1),
            b's': lambda: self._move_cursor(1),
            b'S': lambda: self._move_cursor(1),
            b'\r': self._handle_select,
            b'\n': self._handle_select,
            b'\x20': self._handle_select,
            b' ': self._handle_select,
            b'd': self._handle_select,
            b'D': self._handle_select,
            b'q': self._handle_quit,
            b'a': self._handle_quit,
            b'A': self._handle_quit,
            ESCAPE: self._handle_quit,
            BACKSPACE: self._handle_delete
        }

    def _render(self) -> None:
        os.system('cls' if os.name == 'nt' else 'clear')
        tooltip = " (esc·QA·← | ↑↓·WS | Enter·Space·→)"
        print(f"{TERM_STYLES['YELLOW'] + TERM_STYLES['BOLD']}{self.title}{TERM_STYLES['RESET']}{tooltip}\n")
        
        for idx, item in enumerate(self.items):
            prefix = '→ ' if idx == self.current else '  '
            style = ''
            if idx == self.current:
                style = TERM_STYLES['RED' if self.pending_delete == idx and self.on_delete and 
                                    idx not in self.non_deletable_indices else 'GREEN'] + TERM_STYLES['BOLD']
            print(f"{style}{prefix}{item}{TERM_STYLES['RESET']}")
            
        if self.last_command_output:
            print("\n" + self.last_command_output)
        else:
            print()
    
    def refresh(self) -> None:
        self._render()
        
    def _move_cursor(self, direction: int) -> None:
        self.current = (self.current + direction) % len(self.items)
        self.pending_delete = None
        self._render()
        
    def _handle_extended_key(self) -> None:
        key_map: Dict[bytes, Callable[[], None]] = {
            b'H': partial(self._move_cursor, -1),
            b'P': partial(self._move_cursor, 1),
            b'M': self._handle_select,
            b'K': self._handle_quit,
            b'I': partial(self._move_cursor, -1),
            b'Q': partial(self._move_cursor, 1),
            b'S': self._handle_delete
        }
        
        extended_key: bytes = msvcrt.getch()
        if extended_key in key_map:
            key_map[extended_key]()
        
    def _handle_select(self) -> None:
        if self.on_select:
            self.on_select(self.current)
        self.pending_delete = None
        self._render()
        
    def _handle_delete(self) -> None:
        if self.current in self.non_deletable_indices:
            self.pending_delete = None
        elif self.pending_delete == self.current and self.on_delete:
            self.on_delete(self.current)
            if self.items:
                del self.items[self.current]
                self.current = min(self.current, len(self.items) - 1)
            self.pending_delete = None
        elif self.on_delete:
            self.pending_delete = self.current
        self._render()
        
    def _handle_quit(self) -> None:
        if self.on_quit:
            self.on_quit()
        self.running = False

    def start(self) -> None:
        self._render()
        
        while self.running:
            if msvcrt.kbhit():
                key = msvcrt.getch()
                handler: Optional[Callable[[], None]] = self.key_handlers.get(key)
                if handler:
                    handler()
                elif key.lower() in [b'q', ESCAPE]:
                    self._handle_quit()
            time.sleep(0.01)


class ADBTool:
    def __init__(self) -> None:
        self.devices_dir = './config/devices'
        self.commands_file = './config/commands.conf'
        self.adb_path = './bin/adb.exe' if os.name == 'nt' else 'adb'
        self.current_device: Optional[str] = None
        
        os.makedirs(self.devices_dir, exist_ok=True)
        self.run_adb_command('disconnect')

    def run_adb_command(self, command: str) -> Tuple[str, int]:
        cmd = [self.adb_path]
        
        if self.current_device and not command.startswith(('connect', 'disconnect')):
            cmd.extend(['-s', self.current_device])
        
        cmd.extend(command.split())
        
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return result.stdout, result.returncode
        except Exception as e:
            return str(e), 1

    def get_device_files(self) -> List[str]:
        if not os.path.exists(self.devices_dir):
            return []
        files = [
            (f, os.path.getmtime(os.path.join(self.devices_dir, f)))
            for f in os.listdir(self.devices_dir)
            if f.endswith('.json')
        ]
        return [os.path.join(self.devices_dir, f[0]) for f in sorted(files, key=lambda x: x[1], reverse=True)]

    def load_device(self, path: str) -> Optional[Dict[str, str]]:
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"{TERM_STYLES['RED']}Error loading device file {path}: {str(e)}{TERM_STYLES['RESET']}")
            return None

    def save_device(self, name: str, ip: str, port: str, serial: str) -> bool:
        path = os.path.join(self.devices_dir, f"{name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json")
        try:
            with open(path, 'w') as f:
                json.dump({"name": name, "serial": serial, "ip": ip, "port": port}, f)
            return True
        except Exception as e:
            print(f"{TERM_STYLES['RED']}Error saving device: {str(e)}{TERM_STYLES['RESET']}")
            return False

    def get_available_usb_devices(self) -> List[str]:
        output, _ = self.run_adb_command("devices")
        return [l.split()[0] for l in output.splitlines()[1:] if 'device' in l]

    def get_device_ip(self, device_id: str) -> Optional[str]:
        out, code = self.run_adb_command(f"-s {device_id} shell ip route")
        if code == 0:
            import re
            match = re.search(r'src (\d+\.\d+\.\d+\.\d+)', out)
            return match.group(1) if match else None
        return None

    def connect_to_device(self, ip: str, port: str) -> bool:
        device_id = f"{ip}:{port}"
        out, code = self.run_adb_command(f"connect {device_id}")
        if code == 0 and 'connected' in out.lower():
            self.current_device = device_id
            return True
        return False

    def read_user_input(self, prompt: str = "", allowed_keys: Optional[List[bytes]] = None, hide_input: bool = False) -> Optional[str]:
        print(prompt, end="", flush=True)
        result = ""
        
        while True:
            if msvcrt.kbhit():
                key = msvcrt.getch()
                
                if key == ESCAPE:
                    return None
                elif key in [b'\r', b'\n']:
                    print()
                    return result
                elif key == BACKSPACE:
                    if result:
                        result = result[:-1]
                        print("\b \b", end="", flush=True)
                elif not allowed_keys or key in allowed_keys or key.isalnum():
                    try:
                        char = key.decode('utf-8', errors='ignore')
                        result += char
                        if not hide_input:
                            print(char, end="", flush=True)
                        else:
                            print("*", end="", flush=True)
                    except:
                        pass
            
            time.sleep(0.01)

    def display_message(self, message: str, color: str = 'GREEN', wait: float = 1.0) -> None:
        print(f"{TERM_STYLES[color]}{message}{TERM_STYLES['RESET']}")
        if wait:
            time.sleep(wait)

    def device_menu(self) -> None:
        def build_items() -> Tuple[List[str], Dict[str, str]]:
            files = self.get_device_files()
            items = []
            file_map: Dict[str, str] = {}
            for path in files:
                data = self.load_device(path)
                if data:
                    label = f"{data['name']} ({data['ip']}:{data['port']})"
                else:
                    label = f"Broken: {os.path.basename(path)}"
                items.append(label)
                file_map[label] = path
            items.append("[+] Register new device")
            items.append("[-] Disconnect all devices")
            return items, file_map

        def on_select(idx: int) -> None:
            if idx == len(menu.items) - 2:
                self.register_device()
                new_items, new_file_map = build_items()
                menu.items = new_items
                nonlocal file_map
                file_map = new_file_map
                menu.current = 0
                menu.refresh()
                return
            elif idx == len(menu.items) - 1:
                self.display_message("\nDisconnecting all devices...", 'YELLOW')
                self.run_adb_command('disconnect')
                self.display_message("All devices disconnected.", 'GREEN')
                menu.refresh()
                return

            selected_label = menu.items[idx]
            if selected_label in file_map:
                self._handle_device_connection(file_map[selected_label])
                menu.refresh()

        def on_delete(idx: int) -> None:
            if idx < len(menu.items) - 2:
                selected_label = menu.items[idx]
                if selected_label in file_map:
                    try:
                        os.remove(file_map[selected_label])
                    except Exception as e:
                        self.display_message(f"\nError deleting file: {str(e)}", 'RED')

        def on_quit() -> None:
            self.run_adb_command('disconnect')

        items, file_map = build_items()
        menu: Menu = Menu(
            items=items, 
            title="ADB Device Manager", 
            on_select=on_select, 
            on_delete=on_delete,
            on_quit=on_quit,
            non_deletable_indices=[len(items) - 2, len(items) - 1])
        menu.start()

    def _handle_device_connection(self, device_path: str) -> None:
        data: Optional[Dict[str, str]] = self.load_device(device_path)
        if not data:
            self.display_message("\nInvalid device data!", 'RED')
            return
            
        connected: bool = self.connect_to_device(data['ip'], data['port'])
        
        if not connected:
            self.display_message(f"\nAttempting wireless reconnection to {data['name']}...", 'YELLOW')
            self.run_adb_command('disconnect')
            time.sleep(1)
            connected = self.connect_to_device(data['ip'], data['port'])
        
        if not connected:
            usb_devices = self.get_available_usb_devices()
            device_serial = next(
                (dev for dev in usb_devices if data.get('serial') == self.run_adb_command(f"-s {dev} get-serialno")[0].strip()), None)
                
            if device_serial:
                self.display_message(f"Re-enabling tcpip over USB for {data['name']}...", 'YELLOW')
                self.run_adb_command(f"-s {device_serial} tcpip {data['port']}")
                time.sleep(2)
                connected = self.connect_to_device(data['ip'], data['port'])
                
                if not connected:
                    self.display_message(f"\nFailed to connect to {data['name']} after re-enabling USB tcpip.", 'RED')
            else:
                self.display_message(f"\nDevice {data['name']} not found via USB. Please ensure it's plugged in and try again.", 'RED')
        
        if connected:
            self.command_menu()

    def register_device(self) -> None:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{TERM_STYLES['YELLOW'] + TERM_STYLES['BOLD']}Registering new device...{TERM_STYLES['RESET']}\n")
        print("Press ESC to cancel")
        self.run_adb_command("usb")
        time.sleep(2)

        known_devices: Dict[str, Dict[str, str]] = {}
        for path in self.get_device_files():
            data = self.load_device(path)
            if data:
                if 'serial' in data:
                    known_devices[data['serial']] = data
                if 'ip' in data and 'port' in data:
                    known_devices[f"{data['ip']}:{data['port']}"] = data

        available_usb_devices = [device for device in self.get_available_usb_devices() if ':' not in device]
        unregistered_usb_devices: List[str] = []

        for device_id in available_usb_devices:
            serial = self.run_adb_command(f"-s {device_id} get-serialno")[0].strip()
            if device_id not in known_devices and serial not in known_devices:
                unregistered_usb_devices.append(device_id)
        
        if not unregistered_usb_devices:
            self.display_message("No new unregistered USB devices found.", 'GREEN')
            input("Press Enter to continue...")
            return

        device = unregistered_usb_devices[0] if len(unregistered_usb_devices) == 1 else None
        if not device:
            def on_select(idx: int) -> None:
                nonlocal device
                device = unregistered_usb_devices[idx]
                selector.running = False

            selector: Menu = Menu(
                items=unregistered_usb_devices,
                title="Select New USB Device to Register",
                on_select=on_select)
            selector.start()

            if not device:
                return

        ip = self.get_device_ip(device)
        if not ip:
            self.display_message(f"Unable to get IP address for {device}. Ensure USB debugging is enabled.", 'RED')
            input("Press Enter to continue...")
            return

        serial = self.run_adb_command(f"-s {device} get-serialno")[0].strip()
        if not serial:
            self.display_message(f"Could not retrieve serial number for {device}.", 'RED')
            input("Press Enter to continue...")
            return

        name = self.read_user_input(
            "Device name (press ESC to cancel): ", allowed_keys=[b' ', b'-', b'_', b'.'])
        if not name:
            self.display_message("\nRegistration cancelled or empty name.", 'RED')
            input("Press Enter to continue...")
            return

        for path in self.get_device_files():
            data = self.load_device(path)
            if data and data.get('name') == name:
                self.display_message(f"\nA device with name '{name}' already exists.", 'RED')
                input("Press Enter to continue...")
                return

        port = "5555"
        print(f"Setting up device connection for {name} ({device})...")
        self.run_adb_command(f"-s {device} tcpip {port}")
        time.sleep(2)

        if self.save_device(name, ip, port, serial):
            self.display_message(f"Device {name} registered.", 'GREEN')
            if self.connect_to_device(ip, port):
                self.display_message(f"Connected to {name}!", 'GREEN')
        else:
            self.display_message(f"Failed to connect to {name} after registration. Try selecting it from the device list.", 'YELLOW')

        input("Press Enter to continue...")

    def load_commands(self) -> List[str]:
        if not os.path.exists(self.commands_file):
            return []
        with open(self.commands_file, 'r', encoding='utf-8') as f:
            groups = f.read().split('\n\n')
        return [g.strip() for g in groups if g.strip()]

    def command_menu(self) -> None:
        commands = self.load_commands()
        items = [g.splitlines()[0] for g in commands] if commands else []
        items.append("[+] Add new command")

        def on_select(idx: int) -> None:
            if idx == len(menu.items) - 1:
                self.add_command()
                
                commands = self.load_commands()
                new_items = [g.splitlines()[0] for g in commands] if commands else []
                new_items.append("[+] Add new command")
                menu.items = new_items
                menu.current = len(menu.items) - 2 if len(menu.items) > 1 else 0
                menu.refresh()
                return
                
            commands = self.load_commands()
            selected_command: str = commands[idx]
            menu.last_command_output = f"{TERM_STYLES['YELLOW'] + TERM_STYLES['BOLD']}Executing: {menu.items[idx]}{TERM_STYLES['RESET']}\n"
            menu.refresh()
            
            output: List[str] = []
            for cmd in selected_command.splitlines()[1:]:
                if not cmd.strip():
                    continue
                out: str
                code: int
                out, code = self.run_adb_command(cmd)
                if code == 0:
                    output.append(out)
                else:
                    output.append(f"{TERM_STYLES['RED']}Error (code {code}):{TERM_STYLES['RESET']}\n{out}")
                    break
            
            menu.last_command_output += "".join(output)
            menu.refresh()

        def on_delete(idx: int) -> None:
            commands = self.load_commands()
            if idx < len(commands):
                try:
                    del commands[idx]
                    with open(self.commands_file, 'w', encoding='utf-8') as f:
                        f.write('\n\n'.join(commands))
                    print(f"\r{TERM_STYLES['RED']}Command removed!{TERM_STYLES['RESET']}", end='')
                    time.sleep(0.75)
                    menu.last_command_output = ""
                    menu.refresh()
                except Exception as e:
                    print(f"\r{TERM_STYLES['RED']}Error deleting command: {str(e)}{TERM_STYLES['RESET']}", end='')
                    time.sleep(1)
                    menu.last_command_output = ""
                    menu.refresh()
        
        def on_quit() -> None:
            self.current_device = None
        
        commands = self.load_commands()
        items = [g.splitlines()[0] for g in commands] if commands else []
        items.append("[+] Add new command")

        menu: Menu = Menu(
            items=items, 
            title="ADB Commands", 
            on_select=on_select, 
            on_delete=on_delete,
            on_quit=on_quit,
            non_deletable_indices=[len(items) - 1])
        menu.start()

    def add_command(self) -> None:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{TERM_STYLES['YELLOW'] + TERM_STYLES['BOLD']}Add New Command Group{TERM_STYLES['RESET']}\n")
        print(" - Enter commands. First line is the group name.")
        print("Press ESC to cancel at any time.")
        print("Enter empty line to finish.\n")
        
        lines: List[str] = []
        line_num: int = 1
        
        while True:
            prefix: str = "Name: " if line_num == 1 else f"Cmd {line_num-1}: "
            line = self.read_user_input(prefix)
            
            if line is None:
                return
            elif not line and line_num > 1:
                break
            elif not line and line_num == 1:
                self.display_message("Command group name cannot be empty.", 'RED')
                continue
            
            if line_num == 1 and line in (command.splitlines()[0] for command in self.load_commands()):
                self.display_message("Command group name cannot be a duplicate.", 'RED')
                continue
            
            lines.append(line)
            line_num += 1
                
        if len(lines) < 2:
            return
                
        try:
            with open(self.commands_file, 'a', encoding='utf-8') as f:
                if os.path.exists(self.commands_file) and os.path.getsize(self.commands_file) > 0:
                    f.write('\n\n')
                f.write('\n'.join(lines))
            self.display_message("\nCommand group added successfully.", 'GREEN')
        except Exception as e:
            self.display_message(f"\nError adding command: {str(e)}", 'RED')    
            input("\nPress Enter to continue...")

    def run(self) -> None:
        try:
            print(f"{TERM_STYLES['BOLD']}=== ADB Tool ==={TERM_STYLES['RESET']}\n")
            print("Checking ADB installation...")
            out, code = self.run_adb_command("version")
            if code != 0:
                self.display_message(f"ADB not found or not working.", 'RED')
                print(f"Make sure {self.adb_path} is in the PATH or in the same directory.")
                input("Press Enter to exit...")
                return
                
            print(f"{TERM_STYLES['GREEN']}ADB found:{TERM_STYLES['RESET']} {out.splitlines()[0]}")
            time.sleep(1)
            
            self.device_menu()
            
            print("\nDisconnecting all devices...")
            self.run_adb_command('disconnect')
            self.display_message("\nAll devices disconnected. Goodbye!", 'GREEN', wait=2.0)
            
        except Exception as e:
            self.display_message(f"\nAn error occurred: {str(e)}", 'RED')
            input("Press Enter to exit...")

if __name__ == '__main__':
    ADBTool().run()