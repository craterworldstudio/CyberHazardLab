import ipaddress
import traceback
import time

def check_permission(item, user, mode):
    if user == "root":
        return True
    
    perms = getattr(item, "perms", "rw-rwxr--")
    owner = getattr(item, "owner", "root")
    group = getattr(item, "group", "root")
    
    # mode is 'r', 'w', or 'x'
    # perms is rw-rwxr-- -> [0:3] owner, [3:6] group, [6:9] other
    if len(perms) < 9:
        return True
        
    idx = {'r': 0, 'w': 1, 'x': 2}.get(mode, 0)
    
    if user == owner:
        return perms[idx] != '-'
    # Basic group check (if user matches group name)
    elif user == group:
        return perms[3+idx] != '-'
    else:
        return perms[6+idx] != '-'

class TerminalCommandHandler:
    def __init__(self, sim, ncm=None, state_manager=None):
        self.sim = sim
        self.ncm = ncm
        self.state_manager = state_manager
        

    def _get_interface(self, device, dev_name):
        if self.ncm:
            return self.ncm.get_interface(device.name, dev_name)
        for i in getattr(device, "interfaces", []) or getattr(device, "ports", {}).values():
            if i.name == dev_name:
                return i
        return None

    def get_prompt(self, device):
        vfs = getattr(device, "vfs", None)
        pwd = vfs.pwd() if vfs else "~"
        sessions = getattr(device, "_terminal_sessions", None)
        local_user = getattr(device, 'current_user', 'root')
        if not sessions:
            return f"{local_user}@{device.name.lower()}:[{pwd}]$ "
        curr = sessions[-1]
        if curr.get("state") == "AWAITING_PASSWORD":
            return f"{curr['user']}@{curr['remote_ip']}'s password: "
        if curr.get("state") == "AWAITING_SU_PASSWORD":
            return "Password: "
        if curr.get("state") == "AWAITING_SCP_PASSWORD":
            return f"{curr['user']}@{curr['remote_ip']}'s password: "
        if curr.get("state") == "AWAITING_NANO_INPUT":
            return ""
        if curr.get("state") == "AWAITING_NC_LISTENER":
            return f"[nc listening on {curr.get('port')}] $ "
        if curr.get("state") == "CONNECTED":
            remote_dev = curr.get("remote_device")
            if remote_dev and getattr(remote_dev, "_terminal_sessions", None):
                return self.get_prompt(remote_dev)
            
            remote_vfs = getattr(remote_dev, "vfs", None) if remote_dev else None
            remote_pwd = remote_vfs.pwd() if remote_vfs else "~"
            return f"{getattr(remote_dev, 'current_user', curr['user'])}@{curr['remote_device_name'].lower()}:[{remote_pwd}]$ "
        return f"{local_user}@{device.name.lower()}:[{pwd}]$ "
    def execute(self, device, command_str):
        sessions = getattr(device, "_terminal_sessions", None)
        if sessions:
            curr = sessions[-1]
            if curr.get("state") == "AWAITING_NANO_INPUT":
                if command_str.startswith("__NANO_SAVE__"):
                    new_content = command_str[len("__NANO_SAVE__"):]
                    vfs = getattr(device, "vfs", None)
                    if vfs:
                        from backend.database.fs import File
                        filename = curr["file"]
                        f = vfs.get_item(filename)
                        if not f:
                            f = File(filename)
                            f.owner = getattr(device, "current_user", "root")
                            f.group = getattr(device, "current_user", "root")
                            f.set_path(vfs.curr_fol.path)
                            vfs.curr_fol.add(f)
                        f.contents = new_content
                    device._terminal_sessions.pop()
                    return f"Saved {curr['file']}."
                elif command_str.strip() == "__NANO_CANCEL__":
                    device._terminal_sessions.pop()
                    return f"Nano cancelled."
                else:
                    return ""
                    
        redirect_file = None
        append_mode = False
        if " >> " in command_str:
            parts = command_str.split(" >> ", 1)
            command_str = parts[0].strip()
            redirect_file = parts[1].strip()
            append_mode = True
        elif " > " in command_str:
            parts = command_str.split(" > ", 1)
            command_str = parts[0].strip()
            redirect_file = parts[1].strip()
            append_mode = False

        out = self._execute_inner(device, command_str)

        if redirect_file and getattr(device, "vfs", None):
            vfs = device.vfs
            self._heal_stray_vfs_items(vfs)
            from backend.database.fs import File, Folder
            f = vfs.path_to_tree(redirect_file) if redirect_file.startswith("/") else vfs.get_item(redirect_file)
            
            if f:
                if not check_permission(f, getattr(device, "current_user", "root"), 'w'):
                    return f"bash: {redirect_file}: Permission denied"
            else:
                target_fol, target_name = self._resolve_target_dir_and_name(
                    vfs, redirect_file, create_dirs=True, user=getattr(device, "current_user", "root")
                )
                if not target_fol or not check_permission(target_fol, getattr(device, "current_user", "root"), 'w'):
                    return f"bash: {redirect_file}: Permission denied"
                f = File(target_name)
                f.owner = getattr(device, "current_user", "root")
                f.group = getattr(device, "current_user", "root")
                f.set_path(target_fol.path)
                target_fol.add(f)
            
            if append_mode:
                if isinstance(f.contents, list):
                    f.contents.append(out)
                else:
                    f.contents = str(f.contents) + ("\n" + out if f.contents else out)
            else:
                f.contents = out

            if redirect_file.endswith("ip_forward") or getattr(f, "name", "") == "ip_forward":
                c_str = "".join(f.contents) if isinstance(f.contents, list) else str(f.contents)
                val = "1" in c_str
                if hasattr(device, "ip_forwarding"):
                    device.ip_forwarding = val
                else:
                    device.forwarding_enabled = val
                if self.state_manager:
                    self.state_manager.save()
            return ""
            
        return out

    def _execute_inner(self, device, command_str):
        # 1. Handle active remote terminal session (e.g. SSH)
        sessions = getattr(device, "_terminal_sessions", None)
        if sessions:
            curr = sessions[-1]
            if curr.get("state") == "AWAITING_SU_PASSWORD":
                target_user = curr["target_user"]
                entered_pass = command_str.strip()
                users = getattr(device, "users", {})
                if users.get(target_user) == entered_pass:
                    device.current_user = target_user
                    device._terminal_sessions.pop()
                    return ""
                else:
                    curr["password_attempts"] = curr.get("password_attempts", 0) + 1
                    if curr["password_attempts"] >= 3:
                        device._terminal_sessions.pop()
                        return "su: Authentication failure"
                    return "Password: "
            if curr.get("state") == "AWAITING_PASSWORD":
                entered_pass = command_str.strip()
                from backend.services.ssh import SSHClientDaemon
                client_daemon = SSHClientDaemon(device)
                res = client_daemon.execute_remote(
                    remote_ip=curr["remote_ip"],
                    command="",
                    username=curr["user"],
                    password=entered_pass,
                    port=curr["port"]
                )
                if res.get("success"):
                    curr["state"] = "CONNECTED"
                    curr["password"] = entered_pass
                    remote_dev = curr.get("remote_device")
                    remote_name = curr["remote_device_name"]
                    local_ip = device.interfaces[0].ip if device.interfaces else "127.0.0.1"
                    ssh_svc = next((s for s in getattr(remote_dev, "services", []) if s.name.upper() in ("SSH_SERVER", "SSH")), None) if remote_dev else None
                    custom_motd = (ssh_svc.config.get("motd") or ssh_svc.config.get("banner")) if ssh_svc and getattr(ssh_svc, "config", None) else None
                    if custom_motd:
                        return f"{custom_motd}\nLast login: {time.strftime('%a %b %d %H:%M:%S %Y')} from {local_ip}"
                    return (
                        f"Welcome to AxiomOS on {remote_name}!\n"
                        f" * Documentation:  https://axiomos.org\n"
                        f" * Management:     NCM v4.2\n"
                        f"Last login: {time.strftime('%a %b %d %H:%M:%S %Y')} from {local_ip}"
                    )
                else:
                    curr["password_attempts"] = curr.get("password_attempts", 0) + 1
                    if curr["password_attempts"] >= 3:
                        device._terminal_sessions.pop()
                        return f"Permission denied (publickey,password).\nConnection to {curr['remote_ip']} closed."
                    return "Permission denied, please try again."

            if curr.get("state") == "AWAITING_SCP_PASSWORD":
                entered_pass = command_str.strip()
                from backend.services.ssh import SSHClientDaemon
                client_daemon = SSHClientDaemon(device)
                res = client_daemon.execute_remote(
                    remote_ip=curr["remote_ip"],
                    command="",
                    username=curr["user"],
                    password=entered_pass,
                    port=curr.get("port", 22)
                )
                if res.get("success"):
                    remote_dev = curr.get("remote_device")
                    if remote_dev and hasattr(remote_dev, "vfs"):
                        dest_path = curr["dest_path"]
                        source_content = curr["source_content"]
                        
                        from backend.database.fs import File, Folder
                        parts_path = [p for p in dest_path.split("/") if p]
                        
                        target_fol = remote_dev.vfs.tree
                        filename = "copied_file"
                        
                        if dest_path.startswith("/"):
                            target_fol = remote_dev.vfs.tree
                        else:
                            target_fol = remote_dev.vfs.curr_fol
                            
                        if len(parts_path) > 0:
                            filename = parts_path[-1]
                            for p in parts_path[:-1]:
                                n_fol = target_fol.get_item(p)
                                if not n_fol:
                                    n_fol = Folder(p)
                                    n_fol.set_path(target_fol.path)
                                    target_fol.add(n_fol)
                                target_fol = n_fol
                                
                        existing_file = target_fol.get_item(filename)
                        if existing_file and isinstance(existing_file, Folder):
                            # Copy into folder
                            target_fol = existing_file
                            filename = curr.get("source_filename", "copied_file")
                            existing_file = target_fol.get_item(filename)
                            
                        if existing_file:
                            existing_file.contents = source_content
                        else:
                            new_f = File(filename)
                            new_f.contents = source_content
                            new_f.owner = curr["user"]
                            new_f.group = curr["user"]
                            new_f.set_path(target_fol.path)
                            target_fol.add(new_f)
                            
                        device._terminal_sessions.pop()
                        return f"{filename}\t\t100%\t{len(source_content)}B\t0.0KB/s\t00:00"
                    else:
                        device._terminal_sessions.pop()
                        return "scp: Remote device has no filesystem."
                else:
                    curr["password_attempts"] = curr.get("password_attempts", 0) + 1
                    if curr["password_attempts"] >= 3:
                        device._terminal_sessions.pop()
                        return f"Permission denied (publickey,password).\nLost connection."
                    return "Permission denied, please try again."

            elif curr.get("state") == "AWAITING_NC_LISTENER":
                trimmed = command_str.strip()
                if trimmed in ("exit", "quit", "^C"):
                    p = curr.get("port")
                    device._terminal_sessions.pop()
                    return f"nc listener on port {p} closed."
                if not trimmed:
                    return ""
                return f"[nc listening on port {curr.get('port')} - waiting for connection...]"
            elif curr.get("state") == "CONNECTED":
                trimmed = command_str.strip()
                remote_dev = curr.get("remote_device")
                if curr.get("is_reverse_shell"):
                    if trimmed in ("exit", "logout"):
                        device._terminal_sessions.pop()
                        return "logout"
                    if not trimmed:
                        return ""
                    return self.execute(remote_dev, command_str)

                if remote_dev and getattr(remote_dev, "_terminal_sessions", None):
                    # Forward to remote device (which handles its own nested session/exit)
                    from backend.services.ssh import SSHClientDaemon
                    client_daemon = SSHClientDaemon(device)
                    res = client_daemon.execute_remote(
                        remote_ip=curr["remote_ip"],
                        command=command_str,
                        username=curr["user"],
                        password=curr["password"],
                        port=curr["port"]
                    )
                    return res.get("output", "")

                if trimmed in ("exit", "logout"):
                    orig_user = curr.get("original_ssh_user", curr.get("user"))
                    if remote_dev and getattr(remote_dev, "current_user", "") != orig_user:
                        remote_dev.current_user = orig_user
                        return "exit"
                    remote_ip = curr["remote_ip"]
                    device._terminal_sessions.pop()
                    return f"logout\nConnection to {remote_ip} closed."
                if not trimmed:
                    return ""
                from backend.services.ssh import SSHClientDaemon
                client_daemon = SSHClientDaemon(device)
                res = client_daemon.execute_remote(
                    remote_ip=curr["remote_ip"],
                    command=command_str,
                    username=curr["user"],
                    password=curr["password"],
                    port=curr["port"]
                )
                if not res.get("success"):
                    if res.get("auth_failed"):
                        device._terminal_sessions.pop()
                        return f"Connection to {curr['remote_ip']} closed by remote host."
                    return f"ssh: {res.get('error', 'Unknown error')}"
                return res.get("output", "")

        # 2. Local command execution
        parts = command_str.split()
        if not parts:
            return ""
            
        cmd = parts[0]
        if cmd in ("exit", "logout"):
            return "logout\n[Process completed - AxiomOS local shell cannot be exited]"

        if getattr(device, "status", "ONLINE").upper() == "OFFLINE":
            if cmd == "poweron":
                device.status = "ONLINE"
                if hasattr(device, "interfaces"):
                    for intf in device.interfaces:
                        intf.status = "up"
                if self.state_manager:
                    self.state_manager.save()
                return f"System started. Node {device.name} is now ONLINE."
            return f"System is powered off. Node {device.name} is OFFLINE."

        if cmd == "whoami":
            return getattr(device, "current_user", "root")

        elif cmd in ("poweroff", "shutdown"):
            cur_user = getattr(device, "current_user", "root")
            if cur_user != "root":
                return f"{cmd}: Need to be root."
            device.status = "OFFLINE"
            if hasattr(device, "interfaces"):
                for intf in device.interfaces:
                    intf.status = "down"
            if self.state_manager:
                self.state_manager.save()
            return f"System halted. Node {device.name} powered down."

        elif cmd == "poweron":
            device.status = "ONLINE"
            if hasattr(device, "interfaces"):
                for intf in device.interfaces:
                    intf.status = "up"
            if self.state_manager:
                self.state_manager.save()
            return f"Node {device.name} is now ONLINE."

        if cmd == "help":
            return self._handle_help(parts)
        elif cmd in ("ls", "pwd", "cat", "mkdir", "touch", "rm", "tree", "cd", "scp"):
            return self._handle_vfs_command(device, parts)

        elif cmd == "hostname":
            if len(parts) > 1 and parts[1].strip():
                new_name = parts[1].strip()
                old_name = device.name
                if new_name != old_name:
                    try:
                        self.sim.rename_device(old_name, new_name)
                        if self.state_manager:
                            self.state_manager.rename_device(old_name, new_name)
                        return f"Hostname updated to '{new_name}'"
                    except ValueError as e:
                        return f"hostname: {e}"
            return device.name
        elif cmd == "ip":
            return self._handle_ip(device, parts)
        elif cmd == "arp":
            return self._handle_arp(device, parts)
        elif cmd == "arpspoof":
            return self._handle_arpspoof(device, parts)
        elif cmd == "sysctl":
            return self._handle_sysctl(device, parts)
        elif cmd == "tcpdump":
            return self._handle_tcpdump(device, parts)
        elif cmd == "nmap":
            return self._handle_nmap(device, parts)
        elif cmd == "nc":
            return self._handle_nc(device, parts)
        elif cmd == "ss":
            return self._handle_ss(device, parts)
        elif cmd == "netstat":
            return self._handle_netstat(device, parts)
        elif cmd == "route":
            return self._handle_legacy_route(device, parts)
        elif cmd == "ping":
            return self._handle_ping(device, parts)
        elif cmd == "curl":
            return self._handle_curl(device, parts)
        elif cmd in ("tracert", "traceroute"):
            return self._handle_tracert(device, parts)
        elif cmd == "ifconfig":
            # Just an alias mapping for our ip addr logic
            parts = ["ip", "addr", "show"]
            return self._handle_ip(device, parts)
        elif cmd == "echo":
            return self._handle_echo(device, parts)
        elif cmd == "ssh":
            return self._handle_ssh(device, parts)
        elif cmd == "service":
            return self._handle_service(device, parts)
        elif cmd == "nslookup":
            return self._handle_nslookup(device, parts)
        elif cmd == "keygen":
            return self._handle_keygen(device, parts)
        elif cmd == "su":
            return self._handle_su(device, parts)
        elif cmd == "nano":
            if len(parts) > 1 and parts[1] in ("--help", "-h"):
                return "nano [FILE]\nOpen the nano interactive text editor for FILE.\nType your text, then type ':wq' or 'EOF' on a new line to save and exit."
            if len(parts) < 2:
                return "nano: missing filename"
                
            vfs = getattr(device, "vfs", None)
            if vfs:
                item = vfs.get_item(parts[1])
                if item:
                    if not check_permission(item, getattr(device, "current_user", "root"), 'w'):
                        return f"nano: {parts[1]}: Permission denied"
                else:
                    if not check_permission(vfs.curr_fol, getattr(device, "current_user", "root"), 'w'):
                        return f"nano: cannot create {parts[1]}: Permission denied"
                        
            if not hasattr(device, "_terminal_sessions"):
                device._terminal_sessions = []
                
            content = ""
            if vfs:
                item = vfs.get_item(parts[1])
                if item and hasattr(item, "contents"):
                    content = str(item.contents)
                    
            device._terminal_sessions.append({
                "state": "AWAITING_NANO_INPUT",
                "file": parts[1]
            })
            
            import json
            payload = json.dumps({"filename": parts[1], "content": content})
            return f"__NANO_OPEN__{payload}"
        elif cmd == "update":
            return self._handle_update(device, parts)
        elif cmd == "mount":
            return self._handle_mount(device, parts)
        elif cmd == "umount":
            return self._handle_umount(device, parts)

        else:
            return f"AxiomOS > Command '{cmd}' not recognized."
            
    def _handle_help(self, parts):
        if len(parts) == 1:
            output = "AxiomOS TERMINAL COMMANDS:\n"
            output += "  help       - Show this help message (use 'help [command]' for more info)\n"
            output += "  ping       - Send ICMP ECHO_REQUEST packets\n"
            output += "  tracert    - Trace route to a remote host\n"
            output += "  netstat    - Print network connections and routing tables\n"
            output += "  ss         - Another utility to investigate sockets\n"
            output += "  nmap       - Network exploration tool and port scanner\n"
            output += "  nc         - Arbitrary TCP/UDP connections, listeners and reverse shells\n"
            output += "  arpspoof   - Intercept packets on a switched LAN using ARP poisoning\n"
            output += "  sysctl     - Configure kernel parameters at runtime (e.g. net.ipv4.ip_forward)\n"
            output += "  tcpdump    - Packet analyzer to capture and inspect live or saved network traffic\n"
            output += "  ifconfig   - Configure a network interface\n"
            output += "  ip         - Show / manipulate routing, devices, policy routing and tunnels\n"
            output += "  arp        - Display or manipulate the local ARP cache\n"
            output += "  route      - (Legacy) Display the routing table\n"
            output += "  echo       - Send RFC 862 Echo probe (TCP/UDP)\n"
            output += "  ssh        - Connect to remote host via SSH\n"
            output += "  service    - Manage daemon services\n"
            output += "  nslookup   - Query DNS server for name resolution\n"
            output += "  keygen     - Generates a TSIG key for secure DNS zone transfers\n"
            output += "  su         - Change user ID or become superuser\n"
            output += "  nano       - Text editor\n"
            output += "  update     - Reload and apply system configurations\n"
            output += "  mount      - Mount a new virtual drive\n"
            output += "  umount     - Unmount a virtual drive\n"
            output += "  ls         - List directory contents\n"
            output += "  pwd        - Print working directory\n"
            output += "  cd         - Change directory\n"
            output += "  mkdir      - Make directories\n"
            output += "  touch      - Change file timestamps (create empty file)\n"
            output += "  cat        - Concatenate files and print on the standard output\n"
            output += "  rm         - Remove files or directories\n"
            output += "  tree       - List contents of directories in a tree-like format\n"
            output += "  scp        - Secure copy (remote file copy program)\n"

            output += "  whoami     - Print effective current username\n"
            output += "  poweroff   - Power down / turn off the device (root only)\n"
            output += "  shutdown   - Power down / turn off the device (root only)\n"
            output += "  poweron    - Power on / turn on the device\n"
            output += "  hostname   - Show current system hostname"
            return output
            
        topic = parts[1]
        
        if topic == "echo":
            return """echo - send RFC 862 echo probe to network host
  Usage: echo [-p port] [-t tcp|udp] destination [message]

  Options:
    -p port      Target port number (default: 7)
    -t proto     Transport protocol: tcp or udp (default: tcp)
    destination  Target IP or hostname
    message      Payload string to echo"""
        elif topic == "ssh":
            return """ssh - OpenSSH client / remote terminal execution
  Usage: ssh [-p port] [-P password] [user@]destination [command]

  Options:
    -p port      Target port number (default: 22)
    -P password  Password for user authentication (default: password)
    destination  Target IP or hostname
    command      Optional remote command to execute"""
        elif topic == "ping":
            return """ping - send ICMP ECHO_REQUEST to network hosts
  Usage: ping [-c count] [-i interval] [-s size] [-t ttl] [-q] [-v] destination
  
  Options:
    -c count     Stop after sending count ECHO_REQUEST packets (default: 4)
    -i interval  Wait interval seconds between sending each packet
    -s size      Specify the number of data bytes to be sent (default: 56)
    -t ttl       Set the IP Time to Live
    -q           Quiet output. Nothing is displayed except the summary lines
    -v           Verbose output. Show detailed packet/payload info"""
        elif topic in ("tracert", "traceroute"):
            return "Usage: tracert [-d] [-h maximum_hops] [-w timeout] target_name\n  -d                 Do not resolve addresses to hostnames.\n  -h maximum_hops    Maximum number of hops to search for target.\n  -w timeout         Wait timeout milliseconds for each reply."
        elif topic in ("netstat", "ss"):
            return "Usage: netstat [-a] [-n] [-p] [-t] [-u]\nDisplays active TCP/UDP connections."
        elif topic == "ifconfig":
            return "Usage: ifconfig\nDisplays the status of the currently active interfaces."
        elif topic == "arp":
            return "Usage: arp\nDisplays the legacy ARP cache table."
        elif topic == "service":
            if len(parts) == 2:
                return """service - manage and configure background system daemons
Usage: service COMMAND [args...]

Commands:
  list [-a]              List running services (or all supported services with -a)
  add <name> <proto> <port>
                         Register a new service (e.g. service add DNS UDP 53)
  start <name>           Start/activate a registered daemon
  stop <name>            Stop/deactivate a running daemon
  remove <name>          Unregister and remove a service
  config <name> show     Display current parameters for a service
  config <name> <k>=<v>  Set a configuration parameter (e.g. service config dns tsig_key=abc)

Use 'help service [command]' for detailed information on subcommands."""

            sub = parts[2].lower()
            if sub == "list":
                return """service list - inspect active and available services
Usage: service list [-a]

Options:
  -a    Show all supported services on the system, including inactive ones.
Without options, displays all registered services and their current state."""
            elif sub == "add":
                return """service add - register a new service daemon
Usage: service add <NAME> <PROTOCOL> <PORT>

Arguments:
  NAME      Service identifier (e.g., DNS, DHCP, HTTP, SSH, ECHO)
  PROTOCOL  Transport protocol (TCP or UDP)
  PORT      Listening port number (e.g., 53, 67, 80, 22, 7)"""
            elif sub == "start":
                return """service start - activate a registered service
Usage: service start <NAME>

Spawns the background daemon and begins listening on the configured port."""
            elif sub == "stop":
                return """service stop - deactivate a running service
Usage: service stop <NAME>

Terminates the active daemon process and closes open listener sockets."""
            elif sub == "remove":
                return """service remove - delete a registered service
Usage: service remove <NAME>

Stops and completely unregisters the service from the device."""
            elif sub == "config":
                return """service config - inspect or modify daemon configuration
Usage:
  service config <NAME> show
  service config <NAME> <KEY>=<VALUE>
  service config <NAME> <KEY> <VALUE>

Examples:
  service config DNS show
  service config DNS tsig_key=MySecretKey123
  service config DNS health_interval=60
  service config DNS_CLIENT nameserver=10.0.0.2"""
            else:
                return f"Unknown service command '{sub}'. See 'help service' for available commands."

        elif topic == "route":
            if len(parts) == 2:
                return """route - IP routing table management
Usage: route [COMMAND [args...]]

Commands:
  (no args)                     Display the kernel routing table
  add <dest_net> via <gw>       Install a new route to destination network via gateway
  del <dest_net>                Delete existing route for specified destination

Examples:
  route
  route add 10.0.2.0/24 via 10.0.1.1
  route add 0.0.0.0/0 via 10.0.0.1
  route del 10.0.2.0/24"""
            sub = parts[2].lower()
            if sub == "add":
                return "route add - add static routing entry\nUsage: route add <dest_subnet> via <next_hop_ip>\nExample: route add 192.168.1.0/24 via 10.0.0.1"
            elif sub in ("del", "delete"):
                return "route del - remove static routing entry\nUsage: route del <dest_subnet>\nExample: route del 192.168.1.0/24"
            else:
                return f"Unknown route command '{sub}'. See 'help route'."

        elif topic == "scp":
            return """scp - secure copy over SSH
Usage: scp <source_path> <user>@<remote_ip>:<destination_path>

Arguments:
  source_path        Path to local file on VFS (e.g. tsig.key, /etc/bind/db.local)
  user@remote_ip     Target user and IP address of remote SSH server
  destination_path   Destination file or directory path on remote VFS

Note: Requires the target host to have the SSH service running on port 22."""

        elif topic == "su":
            return """su - switch user identity
Usage: su [USER]

Options/Arguments:
  USER    Target user account (defaults to root if omitted)
Prompts for password unless switching from root to another user."""

        elif topic == "nano":
            return """nano - interactive text editor
Usage: nano <FILE>

Opens the file for editing. If the file does not exist, it will be created.
Use the overlay editor or type ':wq' on a new line to save and exit."""

        elif topic == "update":
            return """update - reload local network & hostname configuration
Usage: update

Reloads /etc/hostname and /etc/network/interfaces and applies changes immediately."""

        elif topic == "mount":
            return """mount - mount storage volume
Usage: mount [NAME]

Mounts a virtual drive under /mnt/[NAME]. Requires root permissions."""

        elif topic == "umount":
            return """umount - unmount storage volume
Usage: umount [NAME]

Unmounts the volume from /mnt/[NAME]. Requires root permissions."""

        elif topic == "keygen":
            return """keygen - cryptographic TSIG key generator
Usage: keygen <FILENAME>

Generates a random 128-bit hex key and saves it to the specified file on VFS.
Used for authenticating DNS AXFR zone transfers."""

        elif topic == "nslookup":
            return """nslookup - query Internet name servers
Usage: nslookup [-type=TYPE] <name> [server] [tsig_key | key_file]

Options:
  -type=TYPE    Query record type: A, CNAME, SRV, PTR, AXFR (default: A)

Arguments:
  name          Domain name, IP address (for PTR), or zone name (for AXFR)
  server        Optional DNS server IP to query (defaults to configured nameserver)
  tsig_key      Optional TSIG key string or path to key file for AXFR zone transfers"""

        elif topic == "hostname":
            return """hostname - show or set system hostname
Usage:
  hostname            Show current system hostname
  hostname <NEW_NAME> Set system hostname"""

        elif topic == "ls":
            return """ls - list directory contents
Usage: ls [OPTIONS] [PATH]

Options:
  -a    Include hidden files (starting with '.')
  -l    Use long listing format"""

        elif topic == "cat":
            return """cat - concatenate and display file contents
Usage: cat <FILE>"""

        elif topic == "rm":
            return """rm - remove files or directories
Usage: rm [-r] <PATH>

Options:
  -r    Remove directories and their contents recursively"""

        elif topic == "mkdir":
            return """mkdir - create directories
Usage: mkdir <DIRECTORY>"""

        elif topic == "touch":
            return """touch - create empty file or update timestamps
Usage: touch <FILE>"""

        elif topic == "cd":
            return """cd - change working directory
Usage: cd [PATH]"""

        elif topic == "pwd":
            return """pwd - print current working directory
Usage: pwd"""

        elif topic == "tree":
            return """tree - list directory tree
Usage: tree"""

        elif topic == "ip":
            if len(parts) == 2:
                output = "Usage: ip [ OPTIONS ] OBJECT { COMMAND | help }\n"
                output += "OBJECT := { link | addr | route | neigh | maddr | dhcp | dhcp-relay }\n"
                output += "Use 'help ip [object]' for detailed information."
                return output
                
            sub_topic = parts[2]
            if sub_topic == "link":
                return "ip link - network device configuration\n  show             - display all interfaces\n  set [dev] up     - enable interface\n  set [dev] down   - disable interface"
            elif sub_topic == "addr":
                return "ip addr - protocol address management\n  show                                - list IP addresses\n  add [ip/cidr] dev [name]            - assign IP address to interface\n  del [ip/cidr] dev [name]            - remove IP address from interface"
            elif sub_topic == "route":
                return "ip route - routing table management\n  show                                      - display routing table\n  add [dest] via [hop] dev [name]           - add new route\n  del [dest]                                - delete route\n  get [ip]                                  - get route for IP\n  flush                                     - clear all routes"
            elif sub_topic == "neigh":
                return "ip neigh - neighbour/arp table management\n  show             - display ARP cache"
            elif sub_topic == "dhcp":
                return "ip dhcp - DHCP Client management\n  client start     - Broadcast DHCPDISCOVER\n  client release   - Release lease and clear IP"
            elif sub_topic == "dhcp-relay":
                return "ip dhcp-relay <target_ip> - Deploy and configure a DHCP relay agent to forward broadcasts"
            elif sub_topic == "maddr":
                return "ip maddr - multicast address management"
            else:
                return f"Unknown ip object '{sub_topic}'"
        elif topic == "ss":
            return """ss - another utility to investigate sockets
Usage: ss [OPTIONS]

Options:
  -t, --tcp        Display TCP sockets
  -u, --udp        Display UDP sockets
  -l, --listening  Display only listening sockets
  -a, --all        Display both listening and non-listening sockets
  -p, --processes  Show process using socket
  -n, --numeric    Do not try to resolve service names"""
        elif topic == "nmap":
            return """nmap - Network exploration tool and security / port scanner
Usage: nmap [Scan Type...] [Options] {target specification}

TARGET SPECIFICATION:
  Can pass hostnames, IP addresses, networks (e.g. 10.0.0.2, 10.0.0.0/24)
SCAN TECHNIQUES:
  -sS/sT: TCP SYN / Connect scan (default)
  -sU: UDP scan
  -sn: Ping scan (disable port scan, host discovery)
PORT SPECIFICATION:
  -p <port ranges>: Only scan specified ports
    Ex: -p22; -p1-100; -p 22,80,443"""
        elif topic == "nc":
            return """nc (netcat) - arbitrary TCP and UDP connections and listens
Usage:
  nc [-v] [-z] hostname port
  nc -l -p port
  nc hostname port -e /bin/sh

Options:
  -l        Listen mode, for inbound connects
  -p port   Local port number
  -v        Verbose mode
  -z        Zero-I/O mode [used for scanning]
  -u        UDP mode
  -e prog   Program to execute after connection (reverse shell)"""
        elif topic == "arpspoof":
            return """arpspoof - intercept packets on a switched LAN using ARP poisoning
Usage:
  arpspoof [-i interface] [-r] -t target_ip host_to_spoof
  arpspoof [-r] target_ip host_to_spoof

Options:
  -i interface  Specify interface to use (default: eth0)
  -r            Poison both target and host bidirectionally to intercept two-way traffic
  -t target_ip  Specify target host whose ARP cache will be poisoned
  host_to_spoof The IP address to spoof (e.g. Default Gateway)"""
        elif topic == "sysctl":
            return """sysctl - configure kernel parameters at runtime
Usage:
  sysctl <variable>
  sysctl -w <variable>=<value>
  sysctl -a

Examples:
  sysctl net.ipv4.ip_forward
  sysctl -w net.ipv4.ip_forward=1
  sysctl -w net.ipv4.ip_forward=0"""
        elif topic == "tcpdump":
            return """tcpdump - dump traffic on a network
Usage:
  tcpdump [-i interface] [-c count] [-w file.pcap] [-r file.pcap] [-v] [expression]

Options:
  -i interface  Listen on specified interface (default: eth0)
  -c count      Exit after receiving count packets
  -w file       Write captured raw packets to file in PCAP format
  -r file       Read and analyze packets from a saved PCAP file
  -v            Verbose output (shows TTL, flags, headers, packet length)
  expression    Optional protocol/host filter (e.g. icmp, tcp, udp, arp, host <ip>)"""
        elif topic == "arp":
            return """arp - manipulate the system ARP cache
Usage:
  arp [-a]                 Display current ARP cache
  arp -s <ip> <hw_addr>    Add a static entry to ARP cache
  arp -d <ip>              Delete an entry from ARP cache"""
        elif topic == "whoami":
            return "whoami - print effective userid\nUsage: whoami"
        elif topic in ("poweroff", "shutdown"):
            return "poweroff / shutdown - power down the local system\nUsage: poweroff\nRequires root privileges."
        elif topic == "poweron":
            return "poweron - power on the system\nUsage: poweron"
        else:
            return f"No manual entry for {topic}"

    def _resolve_target_dir_and_name(self, vfs, file_path, create_dirs=True, user="root"):
        if not file_path:
            return vfs.curr_fol, ""
        
        file_path = file_path.strip()
        if "/" not in file_path:
            return vfs.curr_fol, file_path

        parent_path, base_name = file_path.rsplit("/", 1)
        base_name = base_name.strip()

        if file_path.startswith("/"):
            cur = vfs.tree
            segments = [s for s in parent_path.split("/") if s]
        else:
            cur = vfs.curr_fol
            segments = [s for s in parent_path.split("/") if s]

        from backend.database.fs import Folder
        for seg in segments:
            if not seg or seg == ".":
                continue
            elif seg == "..":
                cur = cur.parent if cur.parent else cur
            else:
                sub = None
                for itm in cur.all:
                    if isinstance(itm, Folder) and itm.name == seg:
                        sub = itm
                        break
                if not sub:
                    if create_dirs:
                        sub = Folder(seg, parent=cur)
                        sub.owner = user
                        sub.group = user
                        sub.perms = "rwxr-xr-x"
                        sub.path = f"{cur.path.rstrip('/')}/{seg}"
                        cur.add(sub)
                    else:
                        return None, base_name
                cur = sub

        return cur, base_name

    def _heal_stray_vfs_items(self, vfs):
        if not vfs or not hasattr(vfs, "tree"):
            return
        from backend.database.fs import File
        strays = [item for item in list(vfs.tree.all) if isinstance(item, File) and "/" in item.name]
        for item in strays:
            old_name = item.name
            target_fol, clean_name = self._resolve_target_dir_and_name(vfs, old_name, create_dirs=True, user=getattr(item, "owner", "root"))
            if target_fol is not None:
                vfs.tree.all.discard(item)
                vfs.tree.visible.discard(item)
                vfs.tree.hidden.discard(item)
                item.name = clean_name
                item.set_path(target_fol.path)
                target_fol.add(item)

    # VFS Command Handlers
    def _handle_vfs_command(self, device, parts):
        cmd = parts[0]
        vfs = getattr(device, "vfs", None)
        if not vfs:
            return f"bash: {cmd}: File system not available on this device"
            
        self._heal_stray_vfs_items(vfs)
            
        # Provide help for VFS commands
        if len(parts) > 1 and parts[1] in ("--help", "-h"):
            if cmd == "pwd": return "pwd - Print name of current/working directory"
            if cmd == "ls": return "ls [OPTION]... [FILE]...\nList information about the FILEs (the current directory by default).\nOptions:\n  -a  do not ignore entries starting with .\n  -l  use a long listing format"
            if cmd == "tree": return "tree - list contents of directories in a tree-like format"
            if cmd == "mkdir": return "mkdir DIRECTORY...\nCreate the DIRECTORY(ies), if they do not already exist."
            if cmd == "touch": return "touch FILE...\nUpdate the access and modification times of each FILE to the current time.\nA FILE argument that does not exist is created empty."
            if cmd == "cat": return "cat [FILE]...\nConcatenate FILE(s) to standard output."
            if cmd == "rm": return "rm [OPTION]... [FILE]...\nRemove (unlink) the FILE(s).\nOptions:\n  -r  remove directories and their contents recursively"
            if cmd == "cd": return "cd [dir]\nChange the shell working directory."
            if cmd == "scp": return "scp <source> <user@host:destination>\nSecure copy (remote file copy program)."

        if cmd == "pwd":
            return vfs.pwd()
            
        elif cmd == "ls":
            flags = [p for p in parts[1:] if p.startswith("-")]
            args = [p for p in parts[1:] if not p.startswith("-")]
            show_hidden = any("a" in f for f in flags)
            
            target = vfs.curr_fol
            if args:
                arg_path = args[0]
                if arg_path in ("/", "~"):
                    target = vfs.tree
                elif arg_path.startswith("/"):
                    target = vfs.path_to_tree(arg_path)
                else:
                    target = vfs.get_item(arg_path)
                    if not target and "/" in arg_path:
                        cur = vfs.curr_fol
                        for seg in arg_path.split("/"):
                            if not seg or seg == ".":
                                continue
                            elif seg == "..":
                                cur = cur.parent if cur.parent else cur
                            else:
                                sub = None
                                for itm in cur.all:
                                    if itm.name == seg:
                                        sub = itm
                                        break
                                cur = sub
                                if not cur:
                                    break
                        target = cur
                if not target:
                    return f"ls: cannot access '{args[0]}': No such file or directory"
                
            from backend.database.fs import Folder, File
            if isinstance(target, File):
                ext = f".{target.ext}" if target.ext else ""
                return f"{target.name}{ext}"

            if not check_permission(target, getattr(device, "current_user", "root"), 'r'):
                return f"ls: cannot open directory '{target.name}': Permission denied"
                
            import io
            from contextlib import redirect_stdout
            f = io.StringIO()
            with redirect_stdout(f):
                if hasattr(target, "disp"):
                    target.disp(h=show_hidden)
            
            return f.getvalue().strip()
            
        elif cmd == "tree":
            if not check_permission(vfs.curr_fol, getattr(device, "current_user", "root"), 'r'):
                return f"tree: cannot open directory '{vfs.curr_fol.name}': Permission denied"
            import io
            from contextlib import redirect_stdout
            f = io.StringIO()
            with redirect_stdout(f):
                print(vfs.curr_fol)
            return f.getvalue().strip()
            
        elif cmd == "mkdir":
            if len(parts) < 2:
                return "mkdir: missing operand"
            if not check_permission(vfs.curr_fol, getattr(device, "current_user", "root"), 'w'):
                return "mkdir: cannot create directory: Permission denied"
            name = parts[1]
            if vfs.get_item(name):
                return f"mkdir: cannot create directory '{name}': File exists"
            from backend.database.fs import Folder
            fol = Folder(name)
            fol.owner = getattr(device, "current_user", "root")
            fol.group = getattr(device, "current_user", "root")
            fol.parent = vfs.curr_fol
            fol.path = vfs.curr_fol.path + name if vfs.curr_fol.path == "/" else vfs.curr_fol.path + "/" + name
            vfs.curr_fol.add(fol, h=name.startswith("."))
            return ""
            
        elif cmd == "touch":
            if len(parts) < 2:
                return "touch: missing file operand"
            if not check_permission(vfs.curr_fol, getattr(device, "current_user", "root"), 'w'):
                return "touch: cannot touch: Permission denied"
            name = parts[1]
            if vfs.get_item(name):
                return ""
            from backend.database.fs import File
            ext = name.split(".")[-1] if "." in name else ""
            n = name.rsplit(".", 1)[0] if "." in name else name
            if name.startswith("."):
                n = name
            f = File(n, ext)
            f.owner = getattr(device, "current_user", "root")
            f.group = getattr(device, "current_user", "root")
            f.set_path(vfs.curr_fol.path)
            f.contents = ""
            vfs.curr_fol.add(f, h=name.startswith("."))
            return ""
            
        elif cmd == "cat":
            if len(parts) < 2:
                return "cat: missing file operand"
            name = parts[1]
            if name.startswith("/"):
                item = vfs.path_to_tree(name)
            else:
                item = vfs.get_item(name)
                if not item and "/" in name:
                    cur = vfs.curr_fol
                    for seg in name.split("/"):
                        if not seg or seg == ".":
                            continue
                        elif seg == "..":
                            cur = cur.parent if cur.parent else cur
                        else:
                            sub = None
                            for itm in cur.all:
                                iname = itm.name + (f".{itm.ext}" if getattr(itm, "ext", None) else "")
                                if iname == seg or itm.name == seg:
                                    sub = itm
                                    break
                            cur = sub
                            if not cur:
                                break
                    item = cur

            from backend.database.fs import File
            if not isinstance(item, File):
                return f"cat: {name}: No such file or directory"
            if not check_permission(item, getattr(device, "current_user", "root"), 'r'):
                return f"cat: {name}: Permission denied"
                
            out = f"========{item.name}========\n"
            if item.contents:
                if isinstance(item.contents, list):
                    out += "\n".join(item.contents)
                elif isinstance(item.contents, (bytes, bytearray)):
                    try:
                        out += item.contents.decode('utf-8')
                    except Exception:
                        out += f"[Binary data: {len(item.contents)} bytes. Use 'tcpdump -r {name}' to view packet capture.]\n"
                else:
                    out += str(item.contents)
            return out
            
        elif cmd == "rm":
            if len(parts) < 2:
                return "rm: missing operand"
            if not check_permission(vfs.curr_fol, getattr(device, "current_user", "root"), 'w'):
                return "rm: cannot remove: Permission denied"
            flags = "".join([p for p in parts[1:] if p.startswith("-")])
            args = [p for p in parts[1:] if not p.startswith("-")]
            if not args:
                return "rm: missing operand"
            name = args[0]
            item = vfs.get_item(name)
            if not item:
                return f"rm: cannot remove '{name}': No such file or directory"
                
            from backend.database.fs import Folder
            if isinstance(item, Folder) and "r" not in flags:
                return f"rm: cannot remove '{name}': Is a directory"
                
            if item in vfs.curr_fol.all:
                vfs.curr_fol.all.remove(item)
            if item in vfs.curr_fol.visible:
                vfs.curr_fol.visible.remove(item)
            if item in vfs.curr_fol.hidden:
                vfs.curr_fol.hidden.remove(item)
            return ""
            
        elif cmd == "cd":
            if len(parts) < 2 or parts[1] in ("~", ""):
                vfs.curr_fol = vfs.tree
                return ""
            if parts[1] == "/":
                vfs.curr_fol = vfs.tree
                return ""
            if parts[1] == "..":
                vfs.jmp_out()
                return ""
            if parts[1] == ".":
                return ""

            target_path = parts[1]
            user = getattr(device, "current_user", "root")

            if target_path.startswith("/"):
                target = vfs.path_to_tree(target_path)
            else:
                target = vfs.get_item(target_path)
                if not target and "/" in target_path:
                    cur = vfs.curr_fol
                    for seg in target_path.split("/"):
                        if not seg or seg == ".":
                            continue
                        elif seg == "..":
                            cur = cur.parent if cur.parent else cur
                        else:
                            sub = None
                            for itm in cur.all:
                                if itm.name == seg:
                                    sub = itm
                                    break
                            cur = sub
                            if not cur:
                                break
                    target = cur

            if not target:
                return f"bash: cd: {target_path}: No such file or directory"

            from backend.database.fs import Folder
            if not isinstance(target, Folder):
                return f"bash: cd: {target_path}: Not a directory"

            if not check_permission(target, user, 'x'):
                return f"bash: cd: {target_path}: Permission denied"

            vfs.curr_fol = target
            return ""

        elif cmd == "scp":
            if len(parts) < 3:
                return "usage: scp <source> <user@host:destination>"
                
            source_path = parts[1]
            dest_str = parts[2]
            
            if "@" not in dest_str or ":" not in dest_str:
                return "scp: invalid destination format. Use user@host:path"
                
            user_host, dest_path = dest_str.split(":", 1)
            username, remote_ip = user_host.split("@", 1)
            
            # Lookup route and remote host
            network = getattr(device, "network", None)
            if not network:
                return "scp: Network offline."
                
            dest_host = network.get_host_by_ip(remote_ip)
            if not dest_host:
                return f"ssh: connect to host {remote_ip} port 22: Connection refused"
            
            vfs = getattr(device, "vfs", None)
            if not vfs:
                return "scp: No local filesystem."
            source_file = vfs.path_to_tree(source_path)
            if not source_file or not hasattr(source_file, "contents"):
                return f"scp: {source_path}: No such file"
                
            if not hasattr(device, "_terminal_sessions"):
                device._terminal_sessions = []
                
            device._terminal_sessions.append({
                "state": "AWAITING_SCP_PASSWORD",
                "user": username,
                "remote_ip": remote_ip,
                "remote_device": dest_host,
                "source_content": source_file.contents,
                "source_filename": source_file.name,
                "dest_path": dest_path,
                "password_attempts": 0
            })
            return self.get_prompt(device)
            
        return f"bash: {cmd}: command not found"

    def _handle_curl(self, device, parts):
        if len(parts) < 2:
            return "Usage: curl [http://]hostname[:port][/path]"

        url = parts[1]
        
        # Remove http:// or https:// if present
        if url.startswith("http://"):
            url = url[7:]
        elif url.startswith("https://"):
            url = url[8:]
            
        path = "/"
        if "/" in url:
            host_port, path = url.split("/", 1)
            path = "/" + path
        else:
            host_port = url

        port = 80
        if ":" in host_port:
            host_str, port_str = host_port.split(":", 1)
            try:
                port = int(port_str)
            except:
                return "curl: Invalid port"
        else:
            host_str = host_port

        network = getattr(device, "network", None)
        if not network:
            return "curl: Network unreachable"

        import time
        from application.dns_resolver import resolve_hostname
        
        target_ip = host_str
        try:
            import ipaddress
            ipaddress.ip_address(target_ip)
        except:
            target_ip = resolve_hostname(device, host_str, timeout=0.5)

        if not target_ip:
            return f"curl: (6) Could not resolve host: {host_str}"

        # Resolve route
        route, out_intf = network.get_route(device, target_ip)
        if not route or not out_intf:
            return f"curl: (7) Failed to connect to {target_ip} port {port}: No route to host"

        dest_node = network.get_host_by_ip(target_ip)
        if not dest_node:
            return f"curl: (7) Failed to connect to {target_ip} port {port}: Connection timed out"

        # Check for service
        http_svc = None
        for svc in dest_node.services:
            if svc.protocol.upper() == "TCP" and svc.port == port and svc.status.lower() == "running":
                http_svc = svc
                break

        if not http_svc:
            return f"curl: (7) Failed to connect to {target_ip} port {port}: Connection refused"

        daemon = dest_node.get_service_daemon(http_svc.name)
        if not daemon:
            return f"curl: (7) Failed to connect to {target_ip} port {port}: Service unavailable"

        request = f"GET {path} HTTP/1.1\r\nHost: {host_str}\r\nUser-Agent: curl/7.68.0\r\nAccept: */*\r\n\r\n"
        
        mock_packet = type("MockPacket", (), {
            "source_ip": out_intf.ip,
            "destination_ip": target_ip,
            "payload": type("MockTransport", (), {"destination_port": port, "source_port": 54322})()
        })()

        from backend.network.tcp import TCPConnection, TCPState
        conn = TCPConnection(local_ip=target_ip, local_port=port, remote_ip=out_intf.ip, remote_port=54322, network=network)
        conn.state = TCPState.ESTABLISHED
        
        start_time = time.time()
        reply = daemon.handle_tcp(request, conn, mock_packet)
        elapsed = time.time() - start_time
        
        if not reply:
            return "curl: (52) Empty reply from server"
            
        return str(reply)

    def _handle_ip(self, device, parts):
        if len(parts) < 2:
            output = "Usage: ip [ OPTIONS ] OBJECT { COMMAND | help }\n"
            output += "OBJECT := { link | addr | route | neigh | maddr }"
            return output
            
        obj = parts[1]
        if obj == "link":
            if len(parts) == 2 or parts[2] == "show":
                output = ""
                for i, intf in enumerate(getattr(device, "interfaces", []) or getattr(device, "ports", {}).values()):
                    state = "UP" if getattr(intf, "status", "up") == "up" else "DOWN"
                    output += f"{i+1}: {intf.name}: <BROADCAST,MULTICAST,{state}> mtu 1500 qdisc fq_codel state {state}\n"
                    output += f"    link/ether {getattr(intf, 'mac', 'unknown')} brd ff:ff:ff:ff:ff:ff\n"
                if not output:
                    output = "No interfaces found."
                return output
            elif len(parts) >= 5 and parts[2] == "set":
                dev_name = parts[3]
                state = parts[4] # up or down
                intf = self._get_interface(device, dev_name)
                if intf:
                    intf.status = "up" if state == "up" else "down"
                    if self.state_manager: self.state_manager.save()
                    return f"Device {dev_name} state set to {state.upper()}."
                else:
                    return f"Cannot find device \"{dev_name}\""
                    
        elif obj == "addr":
            if len(parts) == 2 or parts[2] == "show":
                output = ""
                for i, intf in enumerate(getattr(device, "interfaces", []) or getattr(device, "ports", {}).values()):
                    state = "UP" if getattr(intf, "status", "up") == "up" else "DOWN"
                    output += f"{i+1}: {intf.name}: <BROADCAST,MULTICAST,{state}> mtu 1500 state {state}\n"
                    output += f"    link/ether {getattr(intf, 'mac', 'unknown')} brd ff:ff:ff:ff:ff:ff\n"
                    if getattr(intf, "ip", None) and getattr(intf, "subnet", None):
                        try:
                            net = ipaddress.IPv4Network(intf.subnet, strict=False)
                            cidr = net.prefixlen
                            output += f"    inet {intf.ip}/{cidr} brd {net.broadcast_address} scope global {intf.name}\n"
                        except:
                            output += f"    inet {intf.ip} mask {intf.subnet} scope global {intf.name}\n"
                if not output:
                    output = "No interfaces found."
                return output
            elif len(parts) >= 5 and parts[2] in ("add", "del"):
                action = parts[2]
                ip_cidr = parts[3]
                if "dev" in parts:
                    dev_idx = parts.index("dev")
                    dev_name = parts[dev_idx+1]
                    intf = self._get_interface(device, dev_name)
                    if not intf:
                        return f"Cannot find device \"{dev_name}\""
                    else:
                        if action == "add":
                            try:
                                net = ipaddress.IPv4Interface(ip_cidr)
                                intf.ip = str(net.ip)
                                intf.subnet = str(net.network)
                                if hasattr(device, "_generate_system_files"):
                                    device._generate_system_files()
                                if self.state_manager: self.state_manager.save()
                                return f"Added {ip_cidr} to {dev_name}."
                            except Exception as e:
                                return f"Error: invalid IP/CIDR '{ip_cidr}'"
                        else:
                            intf.ip = None
                            intf.subnet = None
                            if hasattr(device, "_generate_system_files"):
                                device._generate_system_files()
                            if self.state_manager: self.state_manager.save()
                            return f"Deleted IP from {dev_name}."
                else:
                    return "Usage: ip addr {add|del} [ip/cidr] dev [name]"
                    
        elif obj == "route":
            if not hasattr(device, "routes"):
                return "Routing not supported on this device."
            else:
                if len(parts) == 2 or parts[2] in ("show", "list"):
                    output = ""
                    for r in device.routes:
                        intf_name = getattr(r['interface'], 'name', 'None')
                        if r.get('next_hop'):
                            output += f"{r['destination']} via {r['next_hop']} dev {intf_name}\n"
                        else:
                            output += f"{r['destination']} dev {intf_name} scope link\n"
                    if not device.routes:
                        output = "(empty routing table)"
                    return output
                elif len(parts) >= 4 and parts[2] == "add":
                    dest_subnet = parts[3]
                    next_hop = None
                    out_intf_name = None
                    if "via" in parts:
                        next_hop = parts[parts.index("via")+1]
                    if "dev" in parts:
                        out_intf_name = parts[parts.index("dev")+1]
                    
                    out_intf = None
                    if out_intf_name:
                        out_intf = self.ncm.get_interface(device.name, out_intf_name)
                    elif next_hop:
                        for intf in device.interfaces:
                            if intf.subnet and self.ncm.get_subnet(next_hop) == self.ncm.get_subnet(intf.ip):
                                out_intf = intf
                                break
                    if out_intf:
                        device.add_route(dest_subnet, out_intf, next_hop=next_hop)
                        if self.state_manager: self.state_manager.save()
                        return f"Route added: {dest_subnet} via {next_hop or 'DIRECT'} dev {out_intf.name}"
                    else:
                        return "Error: Network unreachable or invalid device"
                elif len(parts) >= 4 and parts[2] == "del":
                    dest_subnet = parts[3]
                    device.routes = [r for r in device.routes if str(r['destination']) != dest_subnet]
                    if self.state_manager: self.state_manager.save()
                    return f"Route deleted: {dest_subnet}"
                elif len(parts) == 4 and parts[2] == "get":
                    dest_ip = parts[3]
                    route, intf = self.sim.network.get_route(device, dest_ip)
                    if route:
                        next_hop = route.get('next_hop')
                        return f"{dest_ip} via {next_hop or 'DIRECT'} dev {getattr(intf, 'name', 'None')}"
                    else:
                        return f"RTNETLINK answers: Network is unreachable"
                elif len(parts) >= 3 and parts[2] == "flush":
                    device.routes = []
                    if self.state_manager: self.state_manager.save()
                    return "Flushed routing table."
                else:
                    return "Usage: ip route { show | add | del | get | flush }"
                    
        elif obj == "dhcp":
            # ip dhcp client {start|release}
            if len(parts) >= 4 and parts[2] == "client":
                action = parts[3]
                if action == "start":
                    if self.ncm:
                        try:
                            self.ncm.add_service(device.name, "DHCP_CLIENT", "UDP", 68)
                        except ValueError:
                            pass # Ignore if it already exists
                            
                        try:
                            self.ncm.start_service(device.name, "DHCP_CLIENT")
                            if self.state_manager: self.state_manager.save()
                            return "DHCP Client started. Broadcasting DHCPDISCOVER..."
                        except Exception as e:
                            return f"Error starting DHCP client: {str(e)}"
                    return "DHCP Client start failed (no NCM context)."
                elif action == "release":
                    if self.ncm:
                        try:
                            self.ncm.stop_service(device.name, "DHCP_CLIENT")
                            self.ncm.remove_service(device.name, "DHCP_CLIENT")
                        except: pass
                        if getattr(device, "interfaces", []):
                            intf = device.interfaces[0]
                            intf.ip = None
                            intf.subnet = None
                            if hasattr(device, "routes"):
                                device.routes = [r for r in device.routes if r.get("destination") != "0.0.0.0/0"]
                        if self.state_manager: self.state_manager.save()
                        return "DHCP lease released. IP cleared."
                return "Usage: ip dhcp client {start|release}"
                
        elif obj == "dhcp-relay":
            # ip dhcp-relay <target_ip>
            if len(parts) >= 3:
                target_ip = parts[2]
                if self.ncm:
                    svc = self.ncm.add_service(device.name, "DHCP_RELAY", "UDP", 67)
                    svc.config = {"target_ip": target_ip}
                    self.ncm.start_service(device.name, "DHCP_RELAY")
                    if self.state_manager: self.state_manager.save()
                    return f"DHCP Relay enabled. Forwarding to {target_ip}."
            return "Usage: ip dhcp-relay <target_ip>"

        elif obj == "neigh":
            has_arp = False
            if len(parts) == 2 or parts[2] == "show":
                output = ""
                for intf in getattr(device, "interfaces", []):
                    if hasattr(intf, "arp") and intf.arp:
                        has_arp = True
                        for ip, mac in intf.arp.cache.items():
                            output += f"{ip} dev {intf.name} lladdr {mac} REACHABLE\n"
                if not has_arp or not output:
                    return "ARP Cache is empty or unsupported."
                return output
            elif len(parts) >= 3 and parts[2] == "flush":
                for intf in getattr(device, "interfaces", []):
                    if hasattr(intf, "arp") and intf.arp:
                        has_arp = True
                        intf.arp.cache = {}
                if has_arp:
                    return "Flushed neighbor table."
                else:
                    return "ARP not supported on this device."
            elif len(parts) >= 6 and parts[2] in ("add", "del") and parts[4] == "dev":
                # ip neigh add 10.0.0.1 dev eth0 lladdr 00:11:22:33:44:55
                action = parts[2]
                target_ip = parts[3]
                dev_name = parts[5]
                mac = parts[7] if len(parts) >= 8 and parts[6] == "lladdr" else "00:00:00:00:00:00"
                
                intf = self._get_interface(device, dev_name)
                if not intf or not hasattr(intf, "arp") or not intf.arp:
                    return f"Cannot find device \"{dev_name}\" or ARP not supported."
                
                if action == "add":
                    intf.arp.cache[target_ip] = mac
                    if self.state_manager: self.state_manager.save()
                    return f"Added {target_ip} at {mac} to {dev_name} ARP cache."
                else:
                    if target_ip in intf.arp.cache:
                        del intf.arp.cache[target_ip]
                        if self.state_manager: self.state_manager.save()
                        return f"Deleted {target_ip} from {dev_name} ARP cache."
                    return f"Entry {target_ip} not found."
            else:
                return "Usage: ip neigh { show | flush | add [ip] dev [name] lladdr [mac] | del [ip] dev [name] }"
                    
        elif obj == "maddr":
            return "Multicast addresses not simulated."
        else:
            return f"Object \"{obj}\" is unknown, try \"ip help\"."

    def _handle_arp(self, device, parts=None):
        parts = parts or ["arp"]
        if len(parts) > 1 and parts[1] in ("--help", "-h"):
            return """arp - manipulate the system ARP cache
Usage:
  arp [-a]                 Display current ARP cache
  arp -s <ip> <hw_addr>    Add a static entry to ARP cache
  arp -d <ip>              Delete an entry from ARP cache"""

        if len(parts) >= 4 and parts[1] == "-s":
            ip_val = parts[2]
            mac_val = parts[3]
            for intf in getattr(device, "interfaces", []):
                if hasattr(intf, "arp") and intf.arp:
                    intf.arp.cache[ip_val] = mac_val
            return f"Added static ARP entry: {ip_val} -> {mac_val}"

        elif len(parts) >= 3 and parts[1] == "-d":
            ip_val = parts[2]
            deleted = False
            for intf in getattr(device, "interfaces", []):
                if hasattr(intf, "arp") and intf.arp and ip_val in intf.arp.cache:
                    del intf.arp.cache[ip_val]
                    deleted = True
            return f"Deleted ARP entry for {ip_val}" if deleted else f"No ARP entry found for {ip_val}"

        output = f"{'Address':<18} {'HWtype':<10} {'HWaddress':<20} {'Flags':<8} {'Iface'}\n"
        has_arp = False
        for intf in getattr(device, "interfaces", []):
            if hasattr(intf, "arp") and intf.arp:
                has_arp = True
                for ip, mac in intf.arp.cache.items():
                    output += f"{ip:<18} {'ether':<10} {mac:<20} {'C':<8} {intf.name}\n"

        if not has_arp:
            return "ARP not supported on this device."
        elif output.strip().endswith("Iface"):
            return "Address                  HWtype     HWaddress            Flags    Iface\n(empty cache)"
        return output.rstrip()

    def _handle_arpspoof(self, device, parts):
        if len(parts) < 3 or (len(parts) > 1 and parts[1] in ("--help", "-h")):
            return """arpspoof - intercept packets on a switched LAN using ARP poisoning
Usage:
  arpspoof [-i interface] [-r] -t target_ip host_to_spoof
  arpspoof [-r] target_ip host_to_spoof

Options:
  -i interface  Specify interface to use (default: eth0)
  -r            Poison both target and host bidirectionally to intercept two-way traffic
  -t target_ip  Specify target host whose ARP cache will be poisoned
  host_to_spoof The IP address to spoof (e.g. Default Gateway)"""

        args = [p for p in parts[1:]]
        bidirectional = False
        if "-r" in args:
            bidirectional = True
            args.remove("-r")
        elif "--bidirectional" in args:
            bidirectional = True
            args.remove("--bidirectional")

        specified_intf = None
        if "-i" in args:
            idx = args.index("-i")
            if idx + 1 < len(args):
                specified_intf = args[idx + 1]
                args.pop(idx + 1)
            args.pop(idx)

        target_ip = None
        host_to_spoof = None
        if "-t" in args:
            idx = args.index("-t")
            if idx + 1 < len(args):
                target_ip = args[idx + 1]
                args.pop(idx + 1)
            args.pop(idx)
            if args:
                host_to_spoof = args[0]
        elif len(args) >= 2:
            target_ip = args[0]
            host_to_spoof = args[1]

        if not target_ip or not host_to_spoof:
            return "Usage: arpspoof [-i interface] [-r] -t target_ip host_to_spoof"

        src_intf = None
        if specified_intf:
            for intf in getattr(device, "interfaces", []):
                if intf.name == specified_intf:
                    src_intf = intf
                    break
        if not src_intf:
            src_intf = device.interfaces[0] if getattr(device, "interfaces", None) else None

        if not src_intf:
            return "arpspoof: No active interface found on this device."

        if getattr(src_intf, "link", None) is None:
            return f"arpspoof: {src_intf.name}: Network is down (no carrier/link). Move device into Access Point range or connect network cable."

        target_dev = None
        target_intf = None
        spoof_dev = None
        spoof_intf = None
        all_devices = list(getattr(self.sim, "hosts", {}).values()) + list(getattr(self.sim, "routers", {}).values())
        for dev in all_devices:
            for intf in getattr(dev, "interfaces", []):
                if getattr(intf, "ip", "") == target_ip:
                    target_dev = dev
                    target_intf = intf
                if getattr(intf, "ip", "") == host_to_spoof:
                    spoof_dev = dev
                    spoof_intf = intf

        if not target_dev or not target_intf:
            return f"arpspoof: Target host {target_ip} not found on the network."

        # Cache legitimate MACs on attacker so hairpin forwarding succeeds immediately
        if hasattr(device, "arp") and device.arp:
            device.arp.cache[target_ip] = target_intf.mac
            if spoof_intf:
                device.arp.cache[host_to_spoof] = spoof_intf.mac

        # Poison target host ARP cache
        if hasattr(target_intf, "arp") and target_intf.arp:
            target_intf.arp.cache[host_to_spoof] = src_intf.mac
        if hasattr(target_dev, "arp") and target_dev.arp:
            target_dev.arp.cache[host_to_spoof] = src_intf.mac

        # If bidirectional, also poison spoofed host (e.g. Gateway)
        if bidirectional and spoof_dev:
            if spoof_intf and hasattr(spoof_intf, "arp") and spoof_intf.arp:
                spoof_intf.arp.cache[target_ip] = src_intf.mac
            if hasattr(spoof_dev, "arp") and spoof_dev.arp:
                spoof_dev.arp.cache[target_ip] = src_intf.mac

        # Transmit real ARP reply frames over the physical link so intermediate switches update their MAC tables
        if src_intf.link is not None:
            from backend.network.frame import EthernetFrame
            from backend.network.packet import ARPPacket
            arp1 = ARPPacket(
                operation="REPLY",
                sender_ip=host_to_spoof,
                sender_mac=src_intf.mac,
                target_ip=target_ip,
                target_mac=target_intf.mac
            )
            frame1 = EthernetFrame(
                source_mac=src_intf.mac,
                destination_mac=target_intf.mac,
                payload=arp1
            )
            src_intf.send(frame1)

            if bidirectional and spoof_intf:
                arp2 = ARPPacket(
                    operation="REPLY",
                    sender_ip=target_ip,
                    sender_mac=src_intf.mac,
                    target_ip=host_to_spoof,
                    target_mac=spoof_intf.mac
                )
                frame2 = EthernetFrame(
                    source_mac=src_intf.mac,
                    destination_mac=spoof_intf.mac,
                    payload=arp2
                )
                src_intf.send(frame2)

        if getattr(device, "network", None):
            from backend.core.event import Event
            device.network.add_event(Event(
                type="ARP_SPOOF_DETECTED",
                severity="CRITICAL",
                source=device.name,
                destination=target_ip,
                protocol="ARP",
                metadata={
                    "attacker_ip": src_intf.ip,
                    "attacker_mac": src_intf.mac,
                    "target_ip": target_ip,
                    "target_host": target_dev.name,
                    "poisoned_ip": host_to_spoof,
                    "bidirectional": bidirectional
                }
            ))

        output = f"[+] Sent ARP reply: {host_to_spoof} is-at {src_intf.mac} to {target_ip}\n"
        output += f"[+] ARP cache poisoned on {target_dev.name} ({target_ip}). Packets for {host_to_spoof} now route to {device.name}.\n"
        if bidirectional:
            sp_name = spoof_dev.name if spoof_dev else host_to_spoof
            output += f"[+] Sent ARP reply: {target_ip} is-at {src_intf.mac} to {host_to_spoof}\n"
            output += f"[+] Bidirectional poisoning active: ARP cache poisoned on {sp_name} ({host_to_spoof}).\n"

        is_fwd = getattr(device, "ip_forwarding", False) or getattr(device, "forwarding_enabled", False)
        if is_fwd:
            output += f"[+] IP forwarding is ENABLED. Intercepted traffic will be forwarded transparently.\n"
            output += f"[*] Tip: Use 'tcpdump -i {src_intf.name}' to monitor or save intercepted packets."
        else:
            output += f"[!] WARNING: IP forwarding is DISABLED. Intercepted packets will be dropped!\n"
            output += f"[*] Enable IP forwarding to relay traffic: sysctl -w net.ipv4.ip_forward=1"

        return output

    def _handle_sysctl(self, device, parts):
        if len(parts) > 1 and parts[1] in ("--help", "-h"):
            return """sysctl - configure kernel parameters at runtime
Usage:
  sysctl <variable>
  sysctl -w <variable>=<value>
  sysctl -a

Examples:
  sysctl net.ipv4.ip_forward
  sysctl -w net.ipv4.ip_forward=1
  sysctl -w net.ipv4.ip_forward=0"""

        if len(parts) == 1 or (len(parts) == 2 and parts[1] in ("-a", "-A")):
            val = "1" if getattr(device, "ip_forwarding", False) or getattr(device, "forwarding_enabled", False) else "0"
            return f"net.ipv4.ip_forward = {val}"

        args = parts[1:]
        is_write = False
        target_pair = None
        if args[0] == "-w":
            is_write = True
            if len(args) > 1:
                target_pair = args[1]
        elif "=" in args[0]:
            is_write = True
            target_pair = args[0]
        else:
            target_pair = args[0]

        if is_write and target_pair:
            if "=" in target_pair:
                k, v = target_pair.split("=", 1)
                k = k.strip()
                v = v.strip()
                if k == "net.ipv4.ip_forward":
                    enabled = (v == "1" or v.lower() in ("true", "yes", "on"))
                    if hasattr(device, "ip_forwarding"):
                        device.ip_forwarding = enabled
                    else:
                        device.forwarding_enabled = enabled
                    if self.state_manager:
                        self.state_manager.save()
                    return f"net.ipv4.ip_forward = {'1' if enabled else '0'}"
                else:
                    return f"error: \"{k}\" is an unknown key"
            else:
                return "sysctl: syntax error in assignment"
        else:
            k = target_pair.strip() if target_pair else ""
            if k == "net.ipv4.ip_forward":
                val = "1" if getattr(device, "ip_forwarding", False) or getattr(device, "forwarding_enabled", False) else "0"
                return f"net.ipv4.ip_forward = {val}"
            else:
                return f"sysctl: cannot stat /proc/sys/{k.replace('.', '/')}: No such file or directory"

    def _handle_tcpdump(self, device, parts):
        if len(parts) > 1 and parts[1] in ("--help", "-h"):
            return """tcpdump - dump traffic on a network
Usage:
  tcpdump [-i interface] [-c count] [-w file.pcap] [-r file.pcap] [-v] [expression]
  tcpdump [-i interface] --stop

Options:
  -i interface  Listen on specified interface (default: first active interface)
  -c count      Exit after receiving count packets
  -w file       Write raw packets to file in PCAP format (enables continuous live background capture)
  -r file       Read and analyze packets from a saved PCAP file
  -v            Verbose output (shows IP headers, TTL, flags, packet length)
  --stop        Stop continuous background file capture
  expression    Protocol or host filter (e.g. icmp, tcp, udp, arp, host <ip>)"""

        if "--stop" in parts or "stop" in parts:
            intf_target = None
            if "-i" in parts:
                idx = parts.index("-i")
                if idx + 1 < len(parts):
                    intf_target = parts[idx + 1]
            stopped = []
            for i_obj in getattr(device, "interfaces", []):
                if intf_target and i_obj.name != intf_target:
                    continue
                if getattr(i_obj, "active_pcap_file", None) is not None:
                    i_obj.active_pcap_file = None
                    stopped.append(i_obj.name)
            if stopped:
                return f"tcpdump: stopped continuous capture on {', '.join(stopped)}."
            return "tcpdump: no active background capture running on this device."

        intf_name = None
        count = None
        write_file = None
        read_file = None
        verbose = False
        filter_tokens = []

        i = 1
        while i < len(parts):
            p = parts[i]
            if p == "-i" and i + 1 < len(parts):
                intf_name = parts[i+1]
                i += 2
            elif p == "-c" and i + 1 < len(parts):
                try:
                    count = int(parts[i+1])
                except ValueError:
                    pass
                i += 2
            elif p == "-w" and i + 1 < len(parts):
                write_file = parts[i+1]
                i += 2
            elif p == "-r" and i + 1 < len(parts):
                read_file = parts[i+1]
                i += 2
            elif p == "-v":
                verbose = True
                i += 1
            else:
                filter_tokens.append(p.lower())
                i += 1

        vfs = getattr(device, "vfs", None)

        def matches_filter(ts, frame, tokens):
            if not tokens:
                return True
            payload = getattr(frame, "payload", None)
            p_class = payload.__class__.__name__ if payload else ""
            proto = str(getattr(payload, "protocol", "")).lower()
            src_ip = str(getattr(payload, "source_ip", "")).lower()
            dst_ip = str(getattr(payload, "destination_ip", "")).lower()

            for idx, token in enumerate(tokens):
                if token in ("icmp", "tcp", "udp", "arp"):
                    if token == "arp":
                        if p_class != "ARPPacket":
                            return False
                    elif proto != token and token not in p_class.lower():
                        return False
                elif token == "host" and idx + 1 < len(tokens):
                    target_h = tokens[idx + 1]
                    if target_h not in (src_ip, dst_ip):
                        return False
                elif token.isdigit():
                    l4 = getattr(payload, "payload", None)
                    sp = str(getattr(l4, "source_port", ""))
                    dp = str(getattr(l4, "destination_port", ""))
                    if token not in (sp, dp):
                        return False
            return True

        def format_packet_str(ts, frame, is_verbose=False):
            import time
            ts_sec = int(ts)
            ts_usec = int((ts - ts_sec) * 1_000_000)
            t_str = time.strftime("%H:%M:%S", time.localtime(ts_sec)) + f".{ts_usec:06d}"
            payload = getattr(frame, "payload", None)
            if not payload:
                return f"{t_str} {getattr(frame, 'source_mac', '')} > {getattr(frame, 'destination_mac', '')}: Ethernet"

            p_class = payload.__class__.__name__
            if p_class == "ARPPacket":
                op = str(getattr(payload, "operation", "REQUEST")).upper()
                s_ip = getattr(payload, "sender_ip", "0.0.0.0")
                s_mac = getattr(payload, "sender_mac", "00:00:00:00:00:00")
                t_ip = getattr(payload, "target_ip", "0.0.0.0")
                if "REQ" in op or op == "1":
                    return f"{t_str} ARP, Request who-has {t_ip} tell {s_ip}, length 28"
                else:
                    return f"{t_str} ARP, Reply {s_ip} is-at {s_mac}, length 28"

            src_ip = getattr(payload, "source_ip", "0.0.0.0")
            dst_ip = getattr(payload, "destination_ip", "0.0.0.0")
            proto = str(getattr(payload, "protocol", "IP")).upper()
            ttl = getattr(payload, "ttl", 64)
            l4 = getattr(payload, "payload", None)

            if proto == "ICMP" or (l4 and l4.__class__.__name__ == "ICMPPacket"):
                i_type = str(getattr(l4, "type", "ECHO_REQUEST")).upper()
                if "REPLY" in i_type:
                    desc = "ICMP echo reply, id 1, seq 1, length 64"
                elif "REQUEST" in i_type:
                    desc = "ICMP echo request, id 1, seq 1, length 64"
                else:
                    desc = f"ICMP {i_type}, length 64"
                if is_verbose:
                    return f"{t_str} IP (tos 0x0, ttl {ttl}, id 4660, offset 0, flags [DF], proto ICMP (1), length 84)\n    {src_ip} > {dst_ip}: {desc}"
                return f"{t_str} IP {src_ip} > {dst_ip}: {desc}"

            elif proto == "UDP" or (l4 and l4.__class__.__name__ == "UDPPacket"):
                sp = getattr(l4, "source_port", 0)
                dp = getattr(l4, "destination_port", 0)
                raw = getattr(l4, "payload", "")
                if sp == 53 or dp == 53:
                    if dp == 53:
                        desc = f"5353+ A? {raw} (29)"
                    else:
                        desc = f"5353 1/0/0 A {raw} (45)"
                elif sp in (67, 68) or dp in (67, 68):
                    mtype = getattr(raw, "message_type", "BOOTP/DHCP")
                    desc = f"BOOTP/DHCP, {mtype}, length 300"
                else:
                    desc = f"UDP, length {len(str(raw))}"
                if is_verbose:
                    return f"{t_str} IP (tos 0x0, ttl {ttl}, id 4660, offset 0, proto UDP (17), length {28 + len(str(raw))})\n    {src_ip}.{sp} > {dst_ip}.{dp}: {desc}"
                return f"{t_str} IP {src_ip}.{sp} > {dst_ip}.{dp}: {desc}"

            elif proto == "TCP" or (l4 and l4.__class__.__name__ == "TCPPacket"):
                sp = getattr(l4, "source_port", 0)
                dp = getattr(l4, "destination_port", 0)
                flags_set = getattr(l4, "flags", set())
                flag_str = "".join([f[0].upper() for f in sorted(list(flags_set)) if f]) if flags_set else "."
                seq = getattr(l4, "sequence_number", 0)
                ack = getattr(l4, "acknowledgement_number", 0)
                p_len = len(str(getattr(l4, "payload", "")))
                if is_verbose:
                    return f"{t_str} IP (tos 0x0, ttl {ttl}, id 4660, offset 0, proto TCP (6), length {40 + p_len})\n    {src_ip}.{sp} > {dst_ip}.{dp}: Flags [{flag_str}], seq {seq}, ack {ack}, win 64240, length {p_len}"
                return f"{t_str} IP {src_ip}.{sp} > {dst_ip}.{dp}: Flags [{flag_str}], seq {seq}, ack {ack}, win 64240, length {p_len}"

            return f"{t_str} IP {src_ip} > {dst_ip}: {proto}, length {len(str(getattr(payload, 'payload', '')))}"

        # Handle read from file (-r)
        if read_file:
            if not vfs:
                return "tcpdump: File system not available on this device"
            self._heal_stray_vfs_items(vfs)
            f_item = vfs.path_to_tree(read_file) if read_file.startswith("/") else vfs.get_item(read_file)
            if not f_item:
                return f"tcpdump: {read_file}: No such file or directory"
            from backend.database.fs import File
            if not isinstance(f_item, File):
                return f"tcpdump: {read_file}: Not a regular file"
            
            raw_data = f_item.contents
            if isinstance(raw_data, list):
                raw_data = "\n".join(raw_data)
            if isinstance(raw_data, str):
                raw_data = raw_data.encode('latin1')

            import struct, socket, time
            if len(raw_data) < 24:
                return f"tcpdump: {read_file}: truncated pcap file"
            
            magic = struct.unpack('<I', raw_data[:4])[0]
            if magic not in (0xa1b2c3d4, 0xd4c3b2a1):
                return f"tcpdump: {read_file}: bad dump file format"
            
            offset = 24
            parsed_lines = []
            while offset + 16 <= len(raw_data):
                ts_sec, ts_usec, caplen, origlen = struct.unpack('<IIII', raw_data[offset:offset+16])
                offset += 16
                if offset + caplen > len(raw_data):
                    break
                frame_bytes = raw_data[offset:offset+caplen]
                offset += caplen

                if len(frame_bytes) < 14:
                    continue
                ethertype = struct.unpack('!H', frame_bytes[12:14])[0]
                time_str = time.strftime("%H:%M:%S", time.localtime(ts_sec)) + f".{ts_usec:06d}"

                if ethertype == 0x0806 and len(frame_bytes) >= 42:
                    opcode = struct.unpack('!H', frame_bytes[20:22])[0]
                    s_mac = ":".join(f"{b:02x}" for b in frame_bytes[22:28])
                    s_ip = socket.inet_ntoa(frame_bytes[28:32])
                    t_mac = ":".join(f"{b:02x}" for b in frame_bytes[32:38])
                    t_ip = socket.inet_ntoa(frame_bytes[38:42])
                    if "arp" in filter_tokens or not filter_tokens:
                        if opcode == 1:
                            parsed_lines.append(f"{time_str} ARP, Request who-has {t_ip} tell {s_ip}, length 28")
                        else:
                            parsed_lines.append(f"{time_str} ARP, Reply {s_ip} is-at {s_mac}, length 28")
                elif ethertype == 0x0800 and len(frame_bytes) >= 34:
                    ip_hdr = frame_bytes[14:34]
                    proto = ip_hdr[9]
                    ttl = ip_hdr[8]
                    src_ip = socket.inet_ntoa(ip_hdr[12:16])
                    dst_ip = socket.inet_ntoa(ip_hdr[16:20])
                    l4_bytes = frame_bytes[34:]

                    if filter_tokens:
                        matched = True
                        if "icmp" in filter_tokens and proto != 1: matched = False
                        if "tcp" in filter_tokens and proto != 6: matched = False
                        if "udp" in filter_tokens and proto != 17: matched = False
                        if "host" in filter_tokens:
                            h_idx = filter_tokens.index("host")
                            if h_idx + 1 < len(filter_tokens) and filter_tokens[h_idx+1] not in (src_ip, dst_ip):
                                matched = False
                        if not matched:
                            continue

                    if proto == 1 and len(l4_bytes) >= 2:
                        i_type, i_code = l4_bytes[0], l4_bytes[1]
                        desc = "ICMP echo reply, id 1, seq 1, length 64" if i_type == 0 else "ICMP echo request, id 1, seq 1, length 64"
                        if verbose:
                            parsed_lines.append(f"{time_str} IP (tos 0x0, ttl {ttl}, id 4660, offset 0, flags [DF], proto ICMP (1), length 84)\n    {src_ip} > {dst_ip}: {desc}")
                        else:
                            parsed_lines.append(f"{time_str} IP {src_ip} > {dst_ip}: {desc}")
                    elif proto == 17 and len(l4_bytes) >= 4:
                        sp, dp = struct.unpack('!HH', l4_bytes[:4])
                        desc = f"UDP, length {len(l4_bytes)-8}"
                        if verbose:
                            parsed_lines.append(f"{time_str} IP (tos 0x0, ttl {ttl}, id 4660, offset 0, proto UDP (17), length {len(l4_bytes)})\n    {src_ip}.{sp} > {dst_ip}.{dp}: {desc}")
                        else:
                            parsed_lines.append(f"{time_str} IP {src_ip}.{sp} > {dst_ip}.{dp}: {desc}")
                    elif proto == 6 and len(l4_bytes) >= 14:
                        sp, dp = struct.unpack('!HH', l4_bytes[:4])
                        seq, ack = struct.unpack('!II', l4_bytes[4:12])
                        flags_byte = l4_bytes[13]
                        f_list = []
                        if flags_byte & 0x02: f_list.append("S")
                        if flags_byte & 0x10: f_list.append("A")
                        if flags_byte & 0x01: f_list.append("F")
                        if flags_byte & 0x04: f_list.append("R")
                        f_str = "".join(f_list) or "."
                        if verbose:
                            parsed_lines.append(f"{time_str} IP (tos 0x0, ttl {ttl}, id 4660, offset 0, proto TCP (6), length {len(l4_bytes)})\n    {src_ip}.{sp} > {dst_ip}.{dp}: Flags [{f_str}], seq {seq}, ack {ack}, win 64240, length {max(0, len(l4_bytes)-20)}")
                        else:
                            parsed_lines.append(f"{time_str} IP {src_ip}.{sp} > {dst_ip}.{dp}: Flags [{f_str}], seq {seq}, ack {ack}, win 64240, length {max(0, len(l4_bytes)-20)}")
                    else:
                        parsed_lines.append(f"{time_str} IP {src_ip} > {dst_ip}: proto {proto}")

                if count and len(parsed_lines) >= count:
                    break

            out = f"reading from file {read_file}, link-type EN10MB (Ethernet)\n"
            out += "\n".join(parsed_lines)
            return out

        # Live capture from interface
        intf = None
        if intf_name:
            for i_obj in getattr(device, "interfaces", []):
                if i_obj.name == intf_name:
                    intf = i_obj
                    break
            if not intf:
                return f"tcpdump: {intf_name}: No such device exists"
        else:
            if getattr(device, "interfaces", []):
                intf = device.interfaces[0]
            else:
                return "tcpdump: No active interface found on this device"

        buf = getattr(intf, "pcap_buffer", []) or []
        filtered = [item for item in buf if matches_filter(item[0], item[1], filter_tokens)]

        if write_file:
            if not vfs:
                return "tcpdump: File system not available on this device"
            self._heal_stray_vfs_items(vfs)
            from backend.network.pcap import PCAPWriter
            from backend.database.fs import File, Folder
            
            pcap_bytes = PCAPWriter.build_pcap(filtered)
            
            target_fol, target_name = self._resolve_target_dir_and_name(
                vfs, write_file, create_dirs=True, user=getattr(device, "current_user", "root")
            )
            if not target_fol:
                return f"tcpdump: {write_file}: No such file or directory"
            
            f_item = None
            for itm in target_fol.all:
                if itm.name == target_name:
                    f_item = itm
                    break
            if not f_item:
                f_item = File(target_name)
                f_item.owner = getattr(device, "current_user", "root")
                f_item.group = getattr(device, "current_user", "root")
                f_item.set_path(target_fol.path)
                target_fol.add(f_item)
            
            f_item.contents = pcap_bytes
            intf.active_pcap_file = f_item
            
            num_pkts = len(filtered)
            return (
                f"tcpdump: listening on {intf.name}, link-type EN10MB (Ethernet), capture size 262144 bytes\n"
                f"{num_pkts} packets captured\n"
                f"{num_pkts} packets received by filter\n"
                f"[*] Background capture active: incoming/outgoing traffic will automatically sync to {write_file}.\n"
                f"[*] Run 'tcpdump --stop' to stop background logging."
            )

        num_pkts = len(filtered)
        if count and num_pkts > count:
            to_show = filtered[-count:]
        elif num_pkts > 25:
            to_show = filtered[-25:]
        else:
            to_show = filtered

        header = f"tcpdump: verbose output suppressed, use -v or -vv for full protocol decode\nlistening on {intf.name}, link-type EN10MB (Ethernet), capture size 262144 bytes\n"
        if not to_show:
            return header + "0 packets captured"

        lines = [format_packet_str(ts, frame, verbose) for ts, frame in to_show]
        return header + "\n".join(lines) + f"\n{num_pkts} packets captured\n{num_pkts} packets received by filter"

    def _handle_nmap(self, device, parts):
        if len(parts) < 2 or (len(parts) > 1 and parts[1] in ("--help", "-h")):
            return """Nmap 7.94 ( https://nmap.org )
Usage: nmap [Scan Type...] [Options] {target specification}

TARGET SPECIFICATION:
  Can pass hostnames, IP addresses, networks (e.g. 10.0.0.2, 10.0.0.0/24)
SCAN TECHNIQUES:
  -sS/sT: TCP SYN / Connect scan (default)
  -sU: UDP scan
  -sn: Ping scan (disable port scan, host discovery)
PORT SPECIFICATION:
  -p <port ranges>: Only scan specified ports
    Ex: -p22; -p1-100; -p 22,80,443"""

        args = parts[1:]
        target = None
        ports_to_scan = None
        ping_sweep = False
        proto_filter = "ALL"

        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "-sn":
                ping_sweep = True
            elif arg in ("-sS", "-sT"):
                proto_filter = "TCP"
            elif arg == "-sU":
                proto_filter = "UDP"
            elif arg == "-p":
                if i + 1 < len(args):
                    ports_to_scan = self._parse_nmap_ports(args[i+1])
                    i += 1
                else:
                    return "nmap: -p requires port range argument"
            elif arg.startswith("-p"):
                ports_to_scan = self._parse_nmap_ports(arg[2:])
            elif not arg.startswith("-"):
                target = arg
            i += 1

        if not target:
            return "nmap: missing target specification"

        if ports_to_scan is None and not ping_sweep:
            ports_to_scan = [21, 22, 23, 25, 53, 67, 68, 80, 110, 123, 135, 139, 143, 443, 445, 3389, 8080]

        import ipaddress, time
        output = [f"Starting Nmap 7.94 ( https://nmap.org ) at {time.strftime('%Y-%m-%d %H:%M UTC')}"]

        is_network = False
        target_net = None
        try:
            if "/" in target:
                target_net = ipaddress.IPv4Network(target, strict=False)
                is_network = True
        except Exception:
            is_network = False

        if is_network:
            live_hosts = []
            all_devices = list(getattr(self.sim, "hosts", {}).values()) + list(getattr(self.sim, "routers", {}).values())
            for dev in all_devices:
                for intf in getattr(dev, "interfaces", []):
                    if getattr(intf, "ip", None):
                        try:
                            dev_ip = ipaddress.IPv4Address(intf.ip)
                            if dev_ip in target_net:
                                live_hosts.append((dev, intf))
                        except Exception:
                            pass

            if ping_sweep:
                for dev, intf in live_hosts:
                    output.append(f"Nmap scan report for {dev.name} ({intf.ip})")
                    output.append(f"Host is up (0.0003{len(dev.name)}s latency).")
                    output.append(f"MAC Address: {intf.mac} (Virtual Network Adapter)")
                output.append(f"\nNmap done: {target_net.num_addresses} IP addresses ({len(live_hosts)} hosts up) scanned in 0.42 seconds")
                return "\n".join(output)
            else:
                for dev, intf in live_hosts:
                    output.append(f"\nNmap scan report for {dev.name} ({intf.ip})")
                    output.append(f"Host is up (0.00028s latency).")
                    open_ports = self._scan_device_ports(dev, ports_to_scan, proto_filter)
                    if open_ports:
                        output.append(f"{'PORT':<9} {'STATE':<7} SERVICE")
                        for p, proto, svc_name in open_ports:
                            output.append(f"{f'{p}/{proto}':<9} {'open':<7} {svc_name}")
                    else:
                        output.append("All scanned ports are closed.")
                output.append(f"\nNmap done: {target_net.num_addresses} IP addresses ({len(live_hosts)} hosts up) scanned in 0.88 seconds")
                return "\n".join(output)

        resolved_ip = target
        from application.dns_resolver import resolve_hostname
        net = getattr(device, "network", None)
        if net and not target.replace(".", "").isdigit():
            r = resolve_hostname(target, device)
            if r: resolved_ip = r

        target_dev = None
        all_devices = list(getattr(self.sim, "hosts", {}).values()) + list(getattr(self.sim, "routers", {}).values())
        for dev in all_devices:
            if dev.name.lower() == target.lower():
                target_dev = dev
                break
            for intf in getattr(dev, "interfaces", []):
                if getattr(intf, "ip", "") == resolved_ip:
                    target_dev = dev
                    break
            if target_dev: break

        if not target_dev:
            output.append(f"Note: Host seems down. If it is really up, but blocking our ping probes, try -Pn")
            output.append(f"Nmap done: 1 IP address (0 hosts up) scanned in 2.01 seconds")
            return "\n".join(output)

        output.append(f"Nmap scan report for {target_dev.name} ({resolved_ip})")
        output.append(f"Host is up (0.00035s latency).")

        if ping_sweep:
            intf_mac = target_dev.interfaces[0].mac if target_dev.interfaces else "unknown"
            output.append(f"MAC Address: {intf_mac}")
            output.append(f"Nmap done: 1 IP address (1 host up) scanned in 0.05 seconds")
            return "\n".join(output)

        open_ports = self._scan_device_ports(target_dev, ports_to_scan, proto_filter)
        closed_count = max(0, len(ports_to_scan) - len(open_ports))
        if closed_count > 0:
            output.append(f"Not shown: {closed_count} closed tcp/udp ports (reset)")

        if open_ports:
            output.append(f"{'PORT':<9} {'STATE':<7} SERVICE")
            for p, proto, svc_name in open_ports:
                output.append(f"{f'{p}/{proto}':<9} {'open':<7} {svc_name}")
        else:
            output.append("All scanned ports are closed.")

        output.append(f"\nNmap done: 1 IP address (1 host up) scanned in 0.15 seconds")

        if getattr(device, "network", None):
            from backend.core.event import Event
            device.network.add_event(Event(
                type="PORT_SCAN_DETECTED",
                severity="HIGH",
                source=device.name,
                destination=resolved_ip,
                protocol="TCP/UDP",
                metadata={"target": target_dev.name, "ports": [p[0] for p in open_ports]}
            ))

        return "\n".join(output)

    def _parse_nmap_ports(self, arg):
        ports = []
        for part in arg.split(","):
            part = part.strip()
            if "-" in part:
                try:
                    s, e = part.split("-", 1)
                    s_val = int(s)
                    e_val = int(e)
                    ports.extend(range(s_val, min(e_val + 1, s_val + 1000)))
                except: pass
            else:
                try: ports.append(int(part))
                except: pass
        return ports if ports else [22, 53, 80]

    def _scan_device_ports(self, dev, ports, proto_filter):
        PORT_NAMES = {
            21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "domain",
            67: "dhcps", 68: "dhcpc", 80: "http", 110: "pop3", 123: "ntp",
            135: "msrpc", 139: "netbios-ssn", 143: "imap", 443: "https",
            445: "microsoft-ds", 3389: "ms-wbt-server", 8080: "http-proxy"
        }
        res = []
        for s in getattr(dev, "services", []):
            if getattr(s, "status", "").lower() == "running":
                s_port = getattr(s, "port", 0)
                s_proto = getattr(s, "protocol", "TCP").upper()
                if proto_filter != "ALL" and s_proto != proto_filter:
                    continue
                if s_port in ports:
                    name = PORT_NAMES.get(s_port, s.name.lower())
                    res.append((s_port, s_proto.lower(), name))
        return sorted(res, key=lambda x: x[0])

    def _handle_nc(self, device, parts):
        if len(parts) < 2 or parts[1] in ("--help", "-h"):
            return """nc (netcat) - arbitrary TCP and UDP connections and listens
Usage:
  nc [-v] [-z] hostname port
  nc -l -p port
  nc hostname port -e /bin/sh

Options:
  -l        Listen mode, for inbound connects
  -p port   Local port number
  -v        Verbose mode
  -z        Zero-I/O mode [used for scanning]
  -u        UDP mode
  -e prog   Program to execute after connection (reverse shell)"""

        args = parts[1:]
        is_listen = "-l" in args or any("l" in a for a in args if a.startswith("-") and not a.startswith("--"))
        port = None
        target = None
        exec_prog = None
        is_zero = "-z" in args or any("z" in a for a in args if a.startswith("-") and not a.startswith("--"))

        i = 0
        while i < len(args):
            arg = args[i]
            if arg in ("-p", "--port"):
                if i + 1 < len(args):
                    try: port = int(args[i+1])
                    except: pass
                    i += 1
            elif arg in ("-e", "--exec"):
                if i + 1 < len(args):
                    exec_prog = args[i+1]
                    i += 1
            elif arg.isdigit():
                port = int(arg)
            elif not arg.startswith("-"):
                target = arg
            i += 1

        if is_listen:
            listen_port = port or 4444
            if not hasattr(device, "_terminal_sessions"):
                device._terminal_sessions = []
            device._terminal_sessions.append({
                "state": "AWAITING_NC_LISTENER",
                "port": listen_port
            })
            return f"listening on [any] {listen_port} ..."

        if not target or not port:
            return "Usage: nc [options] hostname port"

        resolved_ip = target
        from application.dns_resolver import resolve_hostname
        net = getattr(device, "network", None)
        if net and not target.replace(".", "").isdigit():
            r = resolve_hostname(target, device)
            if r: resolved_ip = r

        target_dev = None
        all_devices = list(getattr(self.sim, "hosts", {}).values()) + list(getattr(self.sim, "routers", {}).values())
        for dev in all_devices:
            for intf in getattr(dev, "interfaces", []):
                if getattr(intf, "ip", "") == resolved_ip:
                    target_dev = dev
                    break
            if target_dev: break

        if not target_dev:
            return f"nc: connect to {target} port {port} (tcp) failed: Connection refused"

        listener_session = None
        for s in getattr(target_dev, "_terminal_sessions", []):
            if s.get("state") == "AWAITING_NC_LISTENER" and s.get("port") == port:
                listener_session = s
                break

        if exec_prog and listener_session:
            src_ip = device.interfaces[0].ip if device.interfaces else "unknown"
            listener_session["state"] = "CONNECTED"
            listener_session["remote_device"] = device
            listener_session["remote_device_name"] = device.name
            listener_session["remote_ip"] = src_ip
            listener_session["user"] = getattr(device, "current_user", "user")
            listener_session["port"] = port
            listener_session["is_reverse_shell"] = True

            if net:
                from backend.core.event import Event
                net.add_event(Event(
                    type="REVERSE_SHELL_CONNECTED",
                    severity="CRITICAL",
                    source=device.name,
                    destination=target_dev.name,
                    protocol="TCP",
                    port=port,
                    metadata={"victim": device.name, "attacker": target_dev.name, "program": exec_prog}
                ))

            return ""

        is_port_open = False
        svc_name = "unknown"
        for s in getattr(target_dev, "services", []):
            if getattr(s, "port", 0) == port and getattr(s, "status", "").lower() == "running":
                is_port_open = True
                svc_name = getattr(s, "name", "unknown").lower()
                break

        if is_port_open or listener_session:
            if is_zero:
                return f"Connection to {target} {port} port [tcp/{svc_name}] succeeded!"
            if port == 22:
                return "SSH-2.0-AxiomSSH_1.0"
            elif port == 80:
                return "HTTP/1.1 200 OK\r\nServer: AxiomHTTP/1.0\r\nContent-Type: text/html\r\n\r\n<!DOCTYPE html><html><body><h1>Cyber Hazard Lab HTTP Server</h1></body></html>"
            elif port == 7:
                return "Axiom Echo Service Ready"
            else:
                return f"Connected to {target}:{port}. Type exit to close."

        return f"nc: connect to {target} port {port} (tcp) failed: Connection refused"

    PORT_SERVICE_MAP = {
        7: "echo",
        20: "ftp-data",
        21: "ftp",
        22: "ssh",
        23: "telnet",
        25: "smtp",
        53: "domain",
        67: "bootps",
        68: "bootpc",
        69: "tftp",
        80: "http",
        88: "kerberos",
        110: "pop3",
        123: "ntp",
        143: "imap",
        161: "snmp",
        389: "ldap",
        443: "https",
        445: "microsoft-ds",
        636: "ldaps",
        3306: "mysql",
        3389: "ms-wbt-server",
        8080: "http-alt",
    }

    def _fmt_endpoint(self, ip, port, numeric):
        if port is None or port == "*":
            return f"{ip}:*"
        if numeric:
            return f"{ip}:{port}"
        svc = self.PORT_SERVICE_MAP.get(port)
        return f"{ip}:{svc}" if svc else f"{ip}:{port}"

    def _get_device_sockets(self, device):
        sockets = []

        # Determine host primary IP
        dev_ip = "0.0.0.0"
        if hasattr(device, "interfaces") and device.interfaces:
            for iface in device.interfaces:
                if getattr(iface, "ip", None) and iface.ip != "0.0.0.0":
                    dev_ip = iface.ip
                    break

        # 1. Listening services
        if hasattr(device, "services"):
            for srv in device.services:
                if getattr(srv, "status", "").lower() == "running":
                    proto = getattr(srv, "protocol", "tcp").lower()
                    port = getattr(srv, "port", 0)
                    name = getattr(srv, "name", "").lower()

                    # Filter out non-listening client utilities
                    if port <= 0 or name in ("ssh_client", "dns_client"):
                        continue

                    local_addr = dev_ip if dev_ip != "0.0.0.0" else "0.0.0.0"

                    sockets.append({
                        "proto": proto,
                        "state": "LISTEN" if proto == "tcp" else "UNCONN",
                        "is_listen": True,
                        "recv_q": "0",
                        "send_q": "128" if proto == "tcp" else "0",
                        "local_ip": local_addr,
                        "local_port": port,
                        "peer_ip": "*" if proto == "tcp" else "*",
                        "peer_port": None,
                        "pid": 100 + port,
                        "proc": name
                    })

        # 2. NC listeners
        for s in getattr(device, "_terminal_sessions", []):
            if s.get("state") == "AWAITING_NC_LISTENER":
                port = s.get("port", 0)
                local_addr = dev_ip if dev_ip != "0.0.0.0" else "0.0.0.0"
                sockets.append({
                    "proto": "tcp",
                    "state": "LISTEN",
                    "is_listen": True,
                    "recv_q": "0",
                    "send_q": "128",
                    "local_ip": local_addr,
                    "local_port": port,
                    "peer_ip": "*",
                    "peer_port": None,
                    "pid": 1337,
                    "proc": "nc"
                })

        # 3. Established sessions (outgoing from this device)
        dev_ip = device.interfaces[0].ip if (getattr(device, "interfaces", []) and device.interfaces[0].ip != "0.0.0.0") else "127.0.0.1"
        for s in getattr(device, "_terminal_sessions", []):
            if s.get("state") == "CONNECTED":
                port = s.get("port", 22)
                r_ip = s.get("remote_ip", "10.0.0.1")
                l_port = 49152 + (hash(s.get("remote_device_name", "") + str(port)) % 10000)
                sockets.append({
                    "proto": "tcp",
                    "state": "ESTAB",
                    "is_listen": False,
                    "recv_q": "0",
                    "send_q": "0",
                    "local_ip": dev_ip,
                    "local_port": l_port,
                    "peer_ip": r_ip,
                    "peer_port": port,
                    "pid": 2048,
                    "proc": "nc" if s.get("is_reverse_shell") else "ssh"
                })

        # 4. Established sessions (incoming into this device)
        net = getattr(device, "network", None)
        if net and hasattr(net, "hosts"):
            for other_dev in net.hosts.values():
                if other_dev is not device:
                    for s in getattr(other_dev, "_terminal_sessions", []):
                        if s.get("state") == "CONNECTED" and s.get("remote_device") == device:
                            port = s.get("port", 22)
                            other_ip = other_dev.interfaces[0].ip if (getattr(other_dev, "interfaces", []) and other_dev.interfaces[0].ip != "0.0.0.0") else "10.0.0.1"
                            r_port = 49152 + (hash(device.name + str(port)) % 10000)
                            sockets.append({
                                "proto": "tcp",
                                "state": "ESTAB",
                                "is_listen": False,
                                "recv_q": "0",
                                "send_q": "0",
                                "local_ip": dev_ip,
                                "local_port": port,
                                "peer_ip": other_ip,
                                "peer_port": r_port,
                                "pid": 100 + port,
                                "proc": "sshd" if port == 22 else ("nc" if s.get("is_reverse_shell") else "server")
                            })

        return sockets

    def _handle_ss(self, device, parts):
        if len(parts) > 1 and parts[1] in ("--help", "-h"):
            return """ss - another utility to investigate sockets
Usage: ss [OPTIONS]

Options:
  -t, --tcp        Display TCP sockets
  -u, --udp        Display UDP sockets
  -l, --listening  Display only listening sockets
  -a, --all        Display both listening and non-listening sockets
  -p, --processes  Show process using socket
  -n, --numeric    Do not try to resolve service names"""

        flag_chars = set()
        long_flags = set()
        for p in parts[1:]:
            if p.startswith("--"):
                long_flags.add(p.lower())
            elif p.startswith("-"):
                for c in p[1:]:
                    flag_chars.add(c.lower())

        has_t = "t" in flag_chars or "--tcp" in long_flags
        has_u = "u" in flag_chars or "--udp" in long_flags
        if not has_t and not has_u:
            show_tcp = True
            show_udp = True
        else:
            show_tcp = has_t
            show_udp = has_u

        has_l = "l" in flag_chars or "--listening" in long_flags
        has_a = "a" in flag_chars or "--all" in long_flags
        if has_l and not has_a:
            show_listen = True
            show_estab = False
        elif has_a:
            show_listen = True
            show_estab = True
        else:
            show_listen = False
            show_estab = True

        show_proc = "p" in flag_chars or "--processes" in long_flags
        numeric = "n" in flag_chars or "--numeric" in long_flags

        sockets = self._get_device_sockets(device)
        filtered = []
        for s in sockets:
            if s["proto"] == "tcp" and not show_tcp:
                continue
            if s["proto"] == "udp" and not show_udp:
                continue
            if s["is_listen"] and not show_listen:
                continue
            if not s["is_listen"] and not show_estab:
                continue
            filtered.append(s)

        if show_proc:
            header = f"{'Netid':<6} {'State':<10} {'Recv-Q':<7} {'Send-Q':<7} {'Local Address:Port':<24} {'Peer Address:Port':<20} Process"
        else:
            header = f"{'Netid':<6} {'State':<10} {'Recv-Q':<7} {'Send-Q':<7} {'Local Address:Port':<24} {'Peer Address:Port':<20}"

        if not filtered:
            return f"{header}\n(No active sockets found)"

        lines = [header]
        for s in filtered:
            local = self._fmt_endpoint(s["local_ip"], s["local_port"], numeric)
            peer = self._fmt_endpoint(s["peer_ip"], s["peer_port"], numeric) if s["peer_port"] is not None else "*:*"
            if show_proc:
                proc_str = f'users:(("{s["proc"]}",pid={s["pid"]},fd=3))'
                lines.append(f"{s['proto']:<6} {s['state']:<10} {s['recv_q']:<7} {s['send_q']:<7} {local:<24} {peer:<20} {proc_str}")
            else:
                lines.append(f"{s['proto']:<6} {s['state']:<10} {s['recv_q']:<7} {s['send_q']:<7} {local:<24} {peer:<20}")

        return "\n".join(lines)

    def _handle_legacy_route(self, device, parts):
        if not hasattr(device, "routes"):
            return "Routing not supported on this device."
        else:
            if len(parts) == 1:
                output = "Routing Table:\n"
                for r in device.routes:
                    intf_name = getattr(r['interface'], 'name', 'None')
                    next_hop = r.get('next_hop') or 'DIRECT'
                    output += f"{r['destination']} via {next_hop} (dev {intf_name})\n"
                if not device.routes:
                    output += "(empty)\n"
                return output
            elif len(parts) == 4 and parts[1] == "add" and parts[3] == "via":
                return "Usage: route add [dest_subnet] via [next_hop_ip]"
            elif len(parts) == 5 and parts[1] == "add" and parts[3] == "via":
                dest_subnet = parts[2]
                next_hop = parts[4]
                
                out_intf = None
                for intf in device.interfaces:
                    if intf.subnet and self.ncm.get_subnet(next_hop) == self.ncm.get_subnet(intf.ip):
                        out_intf = intf
                        break
                        
                if out_intf:
                    device.add_route(dest_subnet, out_intf, next_hop=next_hop)
                    if self.state_manager: self.state_manager.save()
                    return f"Route added: {dest_subnet} via {next_hop} (dev {out_intf.name})"
                else:
                    return f"Network unreachable: Cannot reach next hop {next_hop}"
            elif len(parts) == 3 and parts[1] == "del":
                dest_subnet = parts[2]
                device.routes = [r for r in device.routes if str(r['destination']) != dest_subnet]
                if self.state_manager: self.state_manager.save()
                return f"Route deleted: {dest_subnet}"
            else:
                return "Usage:\n  route\n  route add [dest_subnet] via [next_hop_ip]\n  route del [dest_subnet]"

    def _handle_ping(self, device, parts):
        if len(parts) < 2:
            return "Usage: ping [-c count] [-i interval] [-s size] [-t ttl] [-q] [-v] target_ip"
        
        count = 4
        interval = 1.0
        size = 56
        ttl = 64
        quiet = False
        verbose = False
        target_ip = None
        
        i = 1
        while i < len(parts):
            p = parts[i]
            if p == "-c" and i + 1 < len(parts):
                try: count = int(parts[i+1]); i += 2; continue
                except: pass
            if p == "-i" and i + 1 < len(parts):
                try: interval = float(parts[i+1]); i += 2; continue
                except: pass
            if p == "-s" and i + 1 < len(parts):
                try: size = int(parts[i+1]); i += 2; continue
                except: pass
            if p == "-t" and i + 1 < len(parts):
                try: ttl = int(parts[i+1]); i += 2; continue
                except: pass
            if p == "-q":
                quiet = True; i += 1; continue
            if p == "-v":
                verbose = True; i += 1; continue
                
            if not p.startswith("-"):
                target_ip = p
                
            i += 1
            
        if not target_ip:
            return "Usage: ping [-c count] [-i interval] [-s size] [-t ttl] [-q] [-v] target_ip"
            
        if not device:
            return "Cannot run ping from this device."
            
        from application.dns_resolver import resolve_hostname
        resolved_ip = resolve_hostname(device, target_ip)
        if not resolved_ip:
            return f"ping: {target_ip}: Name or service not known"
            
        output = f"PING {target_ip} ({resolved_ip}) {size}({size+28}) bytes of data.\n" if not quiet else ""
        success_count = 0
        
        try:
            for j in range(count):
                result = self.sim.ping(device, resolved_ip, ttl=ttl, payload="0"*size)
                
                # Format response
                line = ""
                if result:
                    if isinstance(result, dict):
                        rtype = result.get("type")
                        rsource = result.get("source", "Unknown")
                        rttl = result.get("ttl", ttl)
                        if rtype == "TIME_EXCEEDED":
                            line = f"[DELAY:{int(interval*1000)}]From {rsource} icmp_seq={j+1} Time to live exceeded\n"
                        elif rtype == "DESTINATION_UNREACHABLE":
                            line = f"[DELAY:{int(interval*1000)}]From {rsource} icmp_seq={j+1} Destination Host Unreachable\n"
                        elif rtype == "TIMEOUT":
                            line = f"[DELAY:{int(interval*1000)}]From {target_ip} icmp_seq={j+1} Request timed out\n"
                        else:
                            line = f"[DELAY:{int(interval*1000)}]{size+8} bytes from {rsource}: icmp_seq={j+1} ttl={rttl} time=1 ms\n"
                            success_count += 1
                            
                        if verbose and rtype:
                            line += f"  > [VERBOSE] Packet Type: {rtype}, Source: {rsource}, Payload Size: {len(result.get('payload', ''))}\n"
                    else:
                        line = f"[DELAY:{int(interval*1000)}]{size+8} bytes from {target_ip}: icmp_seq={j+1} ttl={ttl} time=1 ms\n"
                        success_count += 1
                else:
                    line = f"[DELAY:{int(interval*1000)}]From {target_ip} icmp_seq={j+1} Request timed out\n"
                
                if not quiet:
                    output += line
            
            output += f"\n--- {target_ip} ping statistics ---\n"
            output += f"{count} packets transmitted, {success_count} received, {100 - (success_count/count*100 if count else 0):.0f}% packet loss, time {int(count*interval*1000)}ms"
            return output
        except Exception as e:
            return f"Ping failed: {str(e)}"

    def _handle_tracert(self, device, parts):
        max_hops = 30
        timeout = 2000
        resolve = True
        
        args = parts[1:]
        target_ip = None
        
        # Super basic manual arg parsing
        skip_next = False
        for i, arg in enumerate(args):
            if skip_next:
                skip_next = False
                continue
            if arg == "-d":
                resolve = False
            elif arg == "-h" and i + 1 < len(args):
                try: max_hops = int(args[i+1])
                except: pass
                skip_next = True
            elif arg == "-w" and i + 1 < len(args):
                try: timeout = int(args[i+1])
                except: pass
                skip_next = True
            elif not arg.startswith("-"):
                target_ip = arg

        if not target_ip:
            return "Usage: tracert [-d] [-h maximum_hops] [-w timeout] target_name"
            
        from application.dns_resolver import resolve_hostname
        resolved_ip = resolve_hostname(device, target_ip)
        if not resolved_ip:
            return f"Unable to resolve target system name {target_ip}."
            
        output = f"Tracing route to {target_ip} [{resolved_ip}] over a maximum of {max_hops} hops:\n\n"
        
        if not hasattr(self.sim, "traceroute"):
            return "Traceroute is not implemented on the simulation engine."
            
        try:
            hops = self.sim.traceroute(device, resolved_ip, max_hops=max_hops)
            for hop in hops:
                ttl = hop.get("ttl", "*")
                addr = hop.get("address")
                htype = hop.get("type")
                
                if htype == "TIMEOUT":
                    output += f" {ttl:2d}    *        *        *       Request timed out.\n"
                else:
                    output += f" {ttl:2d}    1 ms     1 ms     1 ms    {addr}\n"
                    if htype == "ECHO_REPLY":
                        break
            output += "\nTrace complete."
            return output
        except Exception as e:
            return f"Tracert failed: {str(e)}"

    def _handle_netstat(self, device, parts):
        if len(parts) > 1 and parts[1] in ("--help", "-h"):
            return """netstat - print network connections, routing tables, interface statistics
Usage: netstat [OPTIONS]

Options:
  -t, --tcp        Display TCP sockets
  -u, --udp        Display UDP sockets
  -l, --listening  Display only listening sockets
  -a, --all        Display both listening and non-listening sockets
  -p, --programs   Show PID and program names
  -n, --numeric    Don't resolve names"""

        flag_chars = set()
        long_flags = set()
        for p in parts[1:]:
            if p.startswith("--"):
                long_flags.add(p.lower())
            elif p.startswith("-"):
                for c in p[1:]:
                    flag_chars.add(c.lower())

        has_t = "t" in flag_chars or "--tcp" in long_flags
        has_u = "u" in flag_chars or "--udp" in long_flags
        if not has_t and not has_u:
            show_tcp = True
            show_udp = True
        else:
            show_tcp = has_t
            show_udp = has_u

        has_l = "l" in flag_chars or "--listening" in long_flags
        has_a = "a" in flag_chars or "--all" in long_flags
        if has_l and not has_a:
            show_listen = True
            show_estab = False
        elif has_a:
            show_listen = True
            show_estab = True
        else:
            show_listen = False
            show_estab = True

        show_proc = "p" in flag_chars or "--programs" in long_flags or "--processes" in long_flags
        numeric = "n" in flag_chars or "--numeric" in long_flags

        sockets = self._get_device_sockets(device)
        filtered = []
        for s in sockets:
            if s["proto"] == "tcp" and not show_tcp:
                continue
            if s["proto"] == "udp" and not show_udp:
                continue
            if s["is_listen"] and not show_listen:
                continue
            if not s["is_listen"] and not show_estab:
                continue
            filtered.append(s)

        if show_listen and show_estab:
            title = "Active Internet connections (servers and established)"
        elif show_listen:
            title = "Active Internet connections (only servers)"
        else:
            title = "Active Internet connections (w/o servers)"

        if show_proc:
            cols = f"{'Proto':<5} {'Recv-Q':<7} {'Send-Q':<7} {'Local Address':<23} {'Foreign Address':<23} {'State':<11} PID/Program name"
        else:
            cols = f"{'Proto':<5} {'Recv-Q':<7} {'Send-Q':<7} {'Local Address':<23} {'Foreign Address':<23} {'State':<11}"

        if not filtered:
            return f"{title}\n{cols}\n(No active sockets found)"

        lines = [title, cols]
        for s in filtered:
            local = self._fmt_endpoint(s["local_ip"], s["local_port"], numeric)
            foreign = self._fmt_endpoint(s["peer_ip"], s["peer_port"], numeric) if s["peer_port"] is not None else "0.0.0.0:*"
            state_str = s["state"]
            if s["proto"] == "udp" and s["is_listen"]:
                state_str = ""
            elif state_str == "ESTAB":
                state_str = "ESTABLISHED"

            if show_proc:
                prog_col = f"{s['pid']}/{s['proc']}"
                lines.append(f"{s['proto']:<5} {s['recv_q']:<7} {s['send_q']:<7} {local:<23} {foreign:<23} {state_str:<11} {prog_col}")
            else:
                lines.append(f"{s['proto']:<5} {s['recv_q']:<7} {s['send_q']:<7} {local:<23} {foreign:<23} {state_str:<11}")

        return "\n".join(lines)

    def _handle_echo(self, device, parts):
        if len(parts) < 2:
            return ""
        if len(parts) > 1 and parts[1] in ("--help", "-h"):
            return """echo - send RFC 862 echo probe to network host or print text
  Usage:
    echo [text]
    echo [-p port] [-t tcp|udp] destination [message]"""

        port = 7
        proto = "TCP"
        target_ip = None
        message_parts = []
        has_network_flag = ("-p" in parts or "-t" in parts)

        i = 1
        while i < len(parts):
            p = parts[i]
            if p == "-p" and i + 1 < len(parts):
                try:
                    port = int(parts[i+1])
                    i += 2
                    continue
                except:
                    pass
            if p == "-t" and i + 1 < len(parts):
                proto = parts[i+1].upper()
                i += 2
                continue
            if not target_ip and not p.startswith("-"):
                target_ip = p
                i += 1
                continue
            message_parts.append(p)
            i += 1

        if not target_ip:
            return ""

        message = " ".join(message_parts) if message_parts else "CyberHazardLab Echo Probe"

        if not device or not getattr(device, "interfaces", []):
            if not has_network_flag:
                return " ".join(parts[1:]).strip('"\'')
            return "Device has no network interfaces configured."

        intf = device.interfaces[0]
        if not intf.ip or intf.ip == "0.0.0.0":
            if not has_network_flag:
                return " ".join(parts[1:]).strip('"\'')
            return "Device has no valid IP assigned."

        network = getattr(device, "network", None)
        if not network:
            if not has_network_flag:
                return " ".join(parts[1:]).strip('"\'')
            return "Device is not connected to a network."

        # Resolve destination if hostname given
        dest_node = network.get_host_by_ip(target_ip)
        if not dest_node:
            dest_node = network.get_host(target_ip)
            if dest_node and getattr(dest_node, "interfaces", []):
                target_ip = dest_node.interfaces[0].ip
            else:
                if not has_network_flag:
                    return " ".join(parts[1:]).strip('"\'')
                return f"echo: Could not resolve hostname {target_ip}: Name or service not known"

        route, out_intf = network.get_route(device, target_ip)
        if not route or not out_intf:
            return f"Network is unreachable: No route from {device.name} to {target_ip}"

        # Check if destination has Echo service running on port
        echo_svc = None
        for s in getattr(dest_node, "services", []):
            if s.port == port and s.status.lower() == "running":
                if s.protocol.upper() in (proto, "TCP/UDP", "ALL") or (s.name.upper() == "ECHO" and port == 7):
                    echo_svc = s
                    break

        if not echo_svc:
            if network:
                from backend.core.event import Event
                network.add_event(Event(
                    type=f"{proto}_PORT_CLOSED",
                    severity="WARNING",
                    source=f"{out_intf.ip}:54321",
                    destination=f"{target_ip}:{port}",
                    protocol=proto,
                    metadata={"reason": "Port closed / Echo service not running", "target": target_ip}
                ))
            return f"Connecting to {target_ip}:{port} ({proto})...\nConnection refused: Port {port} is closed on {target_ip} (Echo service not running)."

        # Target has Echo service running -> execute probe
        daemon = dest_node.get_service_daemon(echo_svc.name)
        mock_packet = type("MockPacket", (), {
            "source_ip": out_intf.ip,
            "destination_ip": target_ip,
            "payload": type("MockTransport", (), {"destination_port": port, "source_port": 54321})()
        })()

        if proto == "TCP":
            from backend.network.tcp import TCPConnection, TCPState
            conn = TCPConnection(local_ip=target_ip, local_port=port, remote_ip=out_intf.ip, remote_port=54321, network=network)
            conn.state = TCPState.ESTABLISHED
            reply = daemon.handle_tcp(message, conn, mock_packet)
        else:
            from backend.network.udp import UDPConnection
            conn = UDPConnection(local_ip=target_ip, local_port=port, remote_ip=out_intf.ip, remote_port=54321, network=network)
            reply = daemon.handle_udp(message, conn, mock_packet)

        output = f"Connecting to {target_ip}:{port} ({proto})...\n"
        output += f"Sent: '{message}' ({len(message)} bytes)\n"
        output += f"Received Echo Reply from {target_ip}:{port}: '{reply}' ({len(reply or '')} bytes, RTT < 1ms)"
        return output

    def _handle_ssh(self, device, parts):
        if len(parts) < 2:
            return "Usage: ssh [-p port] [-P password] [user@]destination [command]"

        port = 22
        password = "password"
        user_host = None
        command_parts = []

        i = 1
        while i < len(parts):
            p = parts[i]
            if p == "-p" and i + 1 < len(parts):
                try:
                    port = int(parts[i+1])
                    i += 2
                    continue
                except:
                    pass
            if p == "-P" and i + 1 < len(parts):
                password = parts[i+1]
                i += 2
                continue
            if not user_host and not p.startswith("-"):
                user_host = p
                i += 1
                continue
            command_parts.append(p)
            i += 1

        if not user_host:
            return "Usage: ssh [-p port] [-P password] [user@]destination [command]"

        if "@" in user_host:
            username, remote_host_str = user_host.split("@", 1)
        else:
            username = "admin"
            remote_host_str = user_host

        command = " ".join(command_parts) if command_parts else ""

        network = getattr(device, "network", None)
        if not network:
            return "Device is not connected to a network."

        # Resolve remote_host_str (IP or hostname)
        remote_ip = remote_host_str
        target_device = network.get_host_by_ip(remote_host_str)
        if not target_device:
            target_device = network.get_host(remote_host_str)
            if target_device and getattr(target_device, "interfaces", []):
                remote_ip = target_device.interfaces[0].ip
            else:
                return f"ssh: Could not resolve hostname {remote_host_str}: Name or service not known"

        # Check route to destination
        route, intf = network.get_route(device, remote_ip)
        if not route or not intf:
            return f"ssh: connect to host {remote_ip} port {port}: No route to host"

        # Check if destination host exists and SSH service is listening
        ssh_server = next((s for s in getattr(target_device, "services", []) if s.protocol.upper() == "TCP" and s.port == port and s.status.lower() == "running"), None)
        if not ssh_server:
            return f"ssh: connect to host {remote_ip} port {port}: Connection refused"

        from backend.services.ssh import SSHClientDaemon
        client_daemon = SSHClientDaemon(device)

        if not command:
            # Interactive continual SSH session
            if not hasattr(device, "_terminal_sessions") or device._terminal_sessions is None:
                device._terminal_sessions = []

            if "-P" in parts:
                res = client_daemon.execute_remote(
                    remote_ip=remote_ip,
                    command="",
                    username=username,
                    password=password,
                    port=port
                )
                if res.get("success"):
                    device._terminal_sessions.append({
                        "state": "CONNECTED",
                        "user": username,
                        "remote_ip": remote_ip,
                        "remote_device_name": target_device.name,
                        "remote_device": target_device,
                        "port": port,
                        "password": password,
                        "password_attempts": 0
                    })
                    local_ip = device.interfaces[0].ip if device.interfaces else "127.0.0.1"
                    ssh_svc = next((s for s in getattr(target_device, "services", []) if s.name.upper() in ("SSH_SERVER", "SSH")), None)
                    custom_motd = (ssh_svc.config.get("motd") or ssh_svc.config.get("banner")) if ssh_svc and getattr(ssh_svc, "config", None) else None
                    if custom_motd:
                        return f"{custom_motd}\nLast login: {time.strftime('%a %b %d %H:%M:%S %Y')} from {local_ip}"
                    return (
                        f"Welcome to AxiomOS on {target_device.name}!\n"
                        f" * Documentation:  https://noxos.org\n"
                        f" * Management:     NCM v2.4\n"
                        f"Last login: {time.strftime('%a %b %d %H:%M:%S %Y')} from {local_ip}"
                    )
                else:
                    device._terminal_sessions.append({
                        "state": "AWAITING_PASSWORD",
                        "user": username,
                        "remote_ip": remote_ip,
                        "remote_device_name": target_device.name,
                        "remote_device": target_device,
                        "port": port,
                        "password": "",
                        "password_attempts": 1
                    })
                    return "Permission denied, please try again."
            else:
                device._terminal_sessions.append({
                    "state": "AWAITING_PASSWORD",
                    "user": username,
                    "remote_ip": remote_ip,
                    "remote_device_name": target_device.name,
                    "remote_device": target_device,
                    "port": port,
                    "password": "",
                    "password_attempts": 0
                })
                return ""

        # Single command execution mode
        res = client_daemon.execute_remote(
            remote_ip=remote_ip,
            command=command,
            username=username,
            password=password,
            port=port
        )

        if not res.get("success"):
            return f"ssh: {res.get('error', 'Unknown error')}"

        return res.get("output", "")

    def _handle_service(self, device, parts):
        if not hasattr(device, "services"):
            return "Services not supported on this device."
            
        if len(parts) == 1 or parts[1] == "list":
            if len(parts) > 2 and parts[2] == "-a":
                output = "AVAILABLE SERVICES:\n"
                supported = ["ECHO", "HTTP", "SSH_SERVER", "SSH_CLIENT", "DHCP", "DHCP_CLIENT", "DHCP_RELAY", "DNS", "DNS_CLIENT"]
                running = {s.name.upper() for s in getattr(device, "services", []) if s.status.lower() == "running"}
                for s in supported:
                    state = " (RUNNING)" if s in running else ""
                    output += f"  - {s}{state}\n"
                return output
                
            if not getattr(device, "services", None):
                return "No services configured. (Use 'service list -a' to view all available types)"
            output = "SERVICES:\n"
            for s in device.services:
                output += f"  [{s.status.upper()}] {s.name} (Port {s.port}/{s.protocol})\n"
            return output
            
        action = parts[1]
        
        if action == "add":
            if len(parts) < 5:
                return "Usage: service add <name> <protocol> <port>"
            name = parts[2].upper()
            proto = parts[3].upper()
            try: port = int(parts[4])
            except: return "Invalid port number"
            
            if self.ncm:
                try:
                    self.ncm.add_service(device.name, name, proto, port)
                    if self.state_manager: self.state_manager.save()
                    return f"Service {name} added."
                except Exception as e:
                    return f"Error: {str(e)}"
            return "Failed to add service (no NCM context)."
            
        elif action == "start":
            if len(parts) < 3: return "Usage: service start <name>"
            name = parts[2].upper()
            if self.ncm:
                try:
                    self.ncm.start_service(device.name, name)
                    if self.state_manager: self.state_manager.save()
                    return f"Service {name} started."
                except Exception as e:
                    return f"Error: {str(e)}"
            return "Failed."
            
        elif action == "stop":
            if len(parts) < 3: return "Usage: service stop <name>"
            name = parts[2].upper()
            if self.ncm:
                try:
                    self.ncm.stop_service(device.name, name)
                    if self.state_manager: self.state_manager.save()
                    return f"Service {name} stopped."
                except Exception as e:
                    return f"Error: {str(e)}"
            return "Failed."
            
        elif action in ("remove", "del"):
            if len(parts) < 3: return "Usage: service remove <name>"
            name = parts[2].upper()
            if self.ncm:
                try:
                    self.ncm.remove_service(device.name, name)
                    if self.state_manager: self.state_manager.save()
                    return f"Service {name} removed."
                except Exception as e:
                    return f"Error: {str(e)}"
            return "Failed."
            
        elif action == "config":
            if len(parts) < 3:
                return "Usage: service config <name> [key=value | key value | show]"
            name = parts[2].upper()
            svc = next((s for s in getattr(device, "services", []) if s.name.upper() == name), None)
            if not svc:
                return f"service: {name} not found on this device."
            
            if len(parts) == 3 or parts[3].lower() == "show":
                daemon = device.get_service_daemon(svc.name)
                effective_cfg = dict(getattr(svc, "config", {}) or {})
                if daemon and hasattr(daemon, "_get_config"):
                    try:
                        d_cfg = daemon._get_config()
                        if isinstance(d_cfg, dict):
                            effective_cfg.update(d_cfg)
                    except Exception:
                        pass
                
                output = f"Configuration for {name}:\n"
                if not effective_cfg:
                    return output + "  (none)"
                
                for k, v in effective_cfg.items():
                    if k == "records" and isinstance(v, list):
                        output += f"  records:\n"
                        output += f"    {'TYPE':<8} {'NAME':<20} {'TARGET':<22} {'STATUS'}\n"
                        output += f"    {'-'*8} {'-'*20} {'-'*22} {'-'*10}\n"
                        for r in v:
                            if isinstance(r, dict):
                                rtype = r.get("type", "A")
                                rname = r.get("name", "@")
                                rtarget = r.get("target", "")
                                raw_status = r.get("status", "ONLINE")
                                rstatus = "STATIC" if rtype.upper() == "PTR" else raw_status
                                output += f"    {rtype:<8} {rname:<20} {rtarget:<22} [{rstatus}]\n"
                            else:
                                output += f"    {r}\n"
                    elif k == "scopes" and isinstance(v, list):
                        output += f"  scopes:\n"
                        output += f"    {'SUBNET':<18} {'START':<16} {'END':<16} {'ROUTER/DNS'}\n"
                        output += f"    {'-'*18} {'-'*16} {'-'*16} {'-'*16}\n"
                        for sc in v:
                            if isinstance(sc, dict):
                                snet = sc.get("subnet", "")
                                p_start = sc.get("pool_start", "")
                                p_end = sc.get("pool_end", "")
                                gw = sc.get("gateway", "")
                                output += f"    {snet:<18} {p_start:<16} {p_end:<16} {gw}\n"
                            else:
                                output += f"    {sc}\n"
                    elif k == "users" and isinstance(v, dict):
                        user_str = ", ".join([f"{u}:{p}" for u, p in v.items()])
                        output += f"  {k} = {user_str}\n"
                    else:
                        output += f"  {k} = {v}\n"
                return output.rstrip()
                
            cfg = dict(getattr(svc, "config", {}))
            raw_kv = " ".join(parts[3:]).strip()
            if "=" in raw_kv:
                k, v = raw_kv.split("=", 1)
            elif len(parts[3:]) >= 2:
                k, v = parts[3], " ".join(parts[4:])
            else:
                return "Usage: service config <name> <key>=<value>"
                
            k = k.strip().lower()
            v = v.strip()
            
            # If configuring users, parse user string (e.g. "admin:dns, root:toor") into dict
            if k == "users":
                if isinstance(v, str):
                    parsed_users = {}
                    # Support comma-separated or space-separated user:pass pairs
                    tokens = [t.strip() for t in v.replace(",", " ").split() if t.strip()]
                    for token in tokens:
                        if ":" in token:
                            u_name, u_pass = token.split(":", 1)
                            parsed_users[u_name.strip()] = u_pass.strip()
                    if parsed_users:
                        cfg["users"] = parsed_users
                        # Synchronize with host system accounts
                        if hasattr(device, "users"):
                            device.users.update(parsed_users)
                    else:
                        cfg["users"] = v
                else:
                    cfg["users"] = v
            else:
                cfg[k] = v
                
            svc.config = cfg
            
            daemon = device.get_service_daemon(svc.name)
            if daemon and hasattr(daemon, "reload_config"):
                daemon.reload_config(svc.config)
                
            if self.state_manager:
                self.state_manager.save()
            return f"Config updated for {name}: {k}='{v}'"
            
        else:
            return "Usage: service {list|add|start|stop|remove|config}"

    def _handle_nslookup(self, device, parts):
        if len(parts) < 2:
            return "Usage: nslookup [-type=any|axfr|srv|ptr|a] <hostname> [dns_server_ip] [tsig_key]"
            
        qtype = "A"
        hostname = ""
        dns_ip = None
        tsig_key = None
        
        args = parts[1:]
        
        for arg in args:
            if arg.startswith("-type="):
                qtype = arg.split("=")[1].upper()
            elif arg.lower() == "ls" and qtype in ("ANY", "AXFR"):
                continue
            elif arg.startswith("-d"):
                continue
            elif not hostname:
                hostname = arg
            elif not dns_ip:
                dns_ip = arg
            elif not tsig_key:
                tsig_key = arg

        if qtype == "ANY" or qtype == "LS":
            qtype = "AXFR"
            
        import ipaddress
        try:
            ipaddress.ip_address(hostname)
            if qtype == "A":  # If user didn't specify type, auto-switch to PTR
                qtype = "PTR"
        except ValueError:
            pass
                
        if not dns_ip:
            for s in getattr(device, "services", []):
                if s.name.upper() in ("DNS_CLIENT", "DNS") and s.status.lower() == "running":
                    dns_ip = s.config.get("nameserver") or s.config.get("dns_server") or s.config.get("dns")
                    if dns_ip:
                        break

        if not dns_ip:
            dns_ip = getattr(device, "dns_server", None)
        
        if not dns_ip:
            return ";; connection timed out; no servers could be reached"
            
        dns_ip = dns_ip.strip()
        
        # If tsig_key is provided and corresponds to a file on local VFS, load key from file
        if tsig_key:
            vfs = getattr(device, "vfs", None)
            if vfs:
                k_file = vfs.get_item(tsig_key) or vfs.path_to_tree(tsig_key)
                if k_file and hasattr(k_file, "contents") and k_file.contents:
                    if isinstance(k_file.contents, list):
                        tsig_key = "".join(k_file.contents).strip()
                    else:
                        tsig_key = str(k_file.contents).strip()

        payload = f"{qtype} {hostname}"
        if tsig_key:
            payload += f" {tsig_key}"
            
        if self.sim:
            from backend.network.packet import Packet, UDPPacket
            
            intf = device.interfaces[0] if device.interfaces else None
            if not intf:
                return "nslookup: Device has no network interfaces."
                
            udp = UDPPacket(source_port=12345, destination_port=53, payload=payload)
            packet = Packet(
                source_ip=intf.ip,
                destination_ip=dns_ip,
                protocol="UDP",
                payload=udp,
                ttl=64
            )
            
            device.last_dns_result = None
            device.send_ip_packet(packet, out_interface=intf)
            
            # Wait up to 500ms for response
            start_wait = time.time()
            while time.time() - start_wait < 0.5:
                if getattr(device, "last_dns_result", None) is not None:
                    break
                time.sleep(0.01)
                
            output = f"Server:\t\t{dns_ip}\nAddress:\t{dns_ip}#53\n\n"
            
            response_str = getattr(device, "last_dns_result", None)
            if response_str:
                if response_str.startswith("DNS_AXFR_RESPONSE:\\n"):
                    output += f"Zone dump for {hostname}:\n"
                    output += response_str.replace("DNS_AXFR_RESPONSE:\\n", "")
                elif response_str.startswith("DNS_RESPONSE: "):
                    ans = response_str.replace("DNS_RESPONSE: ", "")
                    output += f"Non-authoritative answer:\nName:\t{hostname}\nAnswer:\t{ans}"
                elif response_str.startswith("DNS_NXDOMAIN: "):
                    output += f"** server can't find {hostname}: NXDOMAIN"
                elif response_str.startswith("DNS_ERROR: "):
                    err_msg = response_str.replace("DNS_ERROR: ", "")
                    output += f"** server can't find {hostname}: {err_msg}"
                else:
                    output += f"** server failed: {response_str}"
            else:
                output += f";; connection timed out; no servers could be reached"
            return output
        return "Internal Error: Simulation not linked."

    def _handle_keygen(self, device, parts):
        if len(parts) < 2:
            return "Usage: keygen <filename>\nGenerates a TSIG key for secure DNS zone transfers."
        
        filename = parts[1]
        vfs = getattr(device, "vfs", None)
        if not vfs:
            return "keygen: File system not available."
            
        import secrets
        key = secrets.token_hex(16)
        
        if vfs.get_item(filename):
            return f"keygen: File '{filename}' already exists."
            
        from backend.database.fs import File
        ext = filename.split(".")[-1] if "." in filename else "key"
        name = filename.rsplit(".", 1)[0] if "." in filename else filename
        f = File(name, ext)
        f.set_path(vfs.curr_fol.path)
        f.contents = key
        vfs.curr_fol.add(f)
        
        return f"TSIG key generated and saved to {filename}\nKey: {key}"

    def _handle_su(self, device, parts):
        if len(parts) > 1 and parts[1] in ("--help", "-h"):
            return "su [USER]\nChange user ID or become superuser.\nIf USER is not specified, it defaults to root."
            
        target_user = "root" if len(parts) < 2 else parts[1]
        users = getattr(device, "users", {})
        
        if target_user not in users:
            return f"su: user {target_user} does not exist"
            
        current_user = getattr(device, "current_user", "root")
        if current_user == "root" and target_user != "root":
            # root can switch to anyone without password
            device.current_user = target_user
            return ""
            
        if not hasattr(device, "_terminal_sessions"):
            device._terminal_sessions = []
            
        device._terminal_sessions.append({
            "state": "AWAITING_SU_PASSWORD",
            "target_user": target_user,
            "password_attempts": 0
        })
        return "Password: "

    def _handle_update(self, device, parts):
        if len(parts) > 1 and parts[1] in ("--help", "-h"):
            return "update\nReload and apply system configurations from /etc/hostname and /etc/network/interfaces without a reboot."
            
        vfs = getattr(device, "vfs", None)
        if not vfs:
            return "update: file system not available"
            
        output = []
        # Update hostname
        hostname_file = vfs.path_to_tree("/etc/hostname")
        if hostname_file and hasattr(hostname_file, "contents"):
            new_name = str(hostname_file.contents).strip()
            if new_name and new_name != device.name:
                output.append(f"Applying new hostname: {new_name}")
                if hasattr(device, "sim") and device.sim:
                    device.sim.rename_device(device.name, new_name)
                else:
                    device.name = new_name
                    
        # Update network interfaces
        interfaces_file = vfs.path_to_tree("/etc/network/interfaces")
        if interfaces_file and hasattr(interfaces_file, "contents"):
            lines = str(interfaces_file.contents).split("\n")
            current_iface = None
            for line in lines:
                line = line.strip()
                if line.startswith("iface "):
                    parts = line.split()
                    if len(parts) >= 2:
                        current_iface = next((i for i in device.interfaces if i.name == parts[1]), None)
                elif line.startswith("address ") and current_iface:
                    new_ip = line.split()[1]
                    if new_ip != current_iface.ip:
                        current_iface.ip = new_ip
                        output.append(f"Applied new IP {new_ip} to {current_iface.name}")
                        
        return "\n".join(output) if output else "No changes applied."

    def _handle_mount(self, device, parts):
        if len(parts) > 1 and parts[1] in ("--help", "-h"):
            return "mount [NAME]\nMount a new virtual drive under /mnt/[NAME]. Requires root."
        if len(parts) < 2:
            return "mount: missing drive name"
            
        name = parts[1].upper()
        vfs = getattr(device, "vfs", None)
        if not vfs: return "mount: file system not available"
        
        if not check_permission(vfs.tree, getattr(device, "current_user", "root"), 'w'):
            return "mount: only root can mount drives"
            
        mnt = vfs.path_to_tree("/mnt")
        if not mnt:
            return "mount: /mnt directory does not exist"
            
        if mnt.get_item(name):
            return f"mount: /mnt/{name} already exists"
            
        from backend.database.fs import Drive
        new_drive = Drive(name)
        new_drive.owner = "root"
        new_drive.group = "root"
        new_drive.parent = mnt
        new_drive.path = f"/mnt/{name}"
        mnt.add(new_drive)
        if hasattr(device, "_generate_system_files"):
            device._generate_system_files()
        
        return f"Mounted virtual drive {name} at /mnt/{name}"

    def _handle_umount(self, device, parts):
        if len(parts) > 1 and parts[1] in ("--help", "-h"):
            return "umount [NAME]\nUnmount a virtual drive from /mnt/[NAME]. Requires root."
        if len(parts) < 2:
            return "umount: missing drive name"
            
        name = parts[1].upper()
        vfs = getattr(device, "vfs", None)
        if not vfs: return "umount: file system not available"
        
        if not check_permission(vfs.tree, getattr(device, "current_user", "root"), 'w'):
            return "umount: only root can unmount drives"
            
        mnt = vfs.path_to_tree("/mnt")
        if not mnt:
            return "umount: /mnt directory does not exist"
            
        drive = mnt.get_item(name)
        if not drive:
            return f"umount: /mnt/{name} not found"
            
        if drive in mnt.all: mnt.all.remove(drive)
        if drive in mnt.visible: mnt.visible.remove(drive)
        if drive in mnt.hidden: mnt.hidden.remove(drive)
        
        if hasattr(device, "_generate_system_files"):
            device._generate_system_files()

        return f"Unmounted /mnt/{name}"
