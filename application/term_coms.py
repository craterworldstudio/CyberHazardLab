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
        if curr.get("state") == "CONNECTED":
            remote_dev = curr.get("remote_device")
            if remote_dev and getattr(remote_dev, "_terminal_sessions", None):
                return self.get_prompt(remote_dev)
            
            remote_vfs = getattr(remote_dev, "vfs", None) if remote_dev else None
            remote_pwd = remote_vfs.pwd() if remote_vfs else "~"
            return f"{curr['user']}@{curr['remote_device_name'].lower()}:[{remote_pwd}]$ "
        return f"{local_user}@{device.name.lower()}:[{pwd}]$ "
    def execute(self, device, command_str):
        sessions = getattr(device, "_terminal_sessions", None)
        if sessions:
            curr = sessions[-1]
            if curr.get("state") == "AWAITING_NANO_INPUT":
                if command_str.strip() == ":wq" or command_str.strip() == "EOF":
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
                        
                        f.contents = "\n".join(curr["content"])
                    device._terminal_sessions.pop()
                    return f"Saved {curr['file']}."
                else:
                    curr["content"].append(command_str)
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
            from backend.database.fs import File
            f = vfs.get_item(redirect_file)
            
            if f:
                if not check_permission(f, getattr(device, "current_user", "root"), 'w'):
                    return f"bash: {redirect_file}: Permission denied"
            else:
                if not check_permission(vfs.curr_fol, getattr(device, "current_user", "root"), 'w'):
                    return f"bash: {redirect_file}: Permission denied"
                f = File(redirect_file)
                f.owner = getattr(device, "current_user", "root")
                f.group = getattr(device, "current_user", "root")
                f.set_path(vfs.curr_fol.path)
                vfs.curr_fol.add(f)
            
            if append_mode:
                if isinstance(f.contents, list):
                    f.contents.append(out)
                else:
                    f.contents = str(f.contents) + ("\n" + out if f.contents else out)
            else:
                f.contents = out
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

            elif curr.get("state") == "CONNECTED":
                trimmed = command_str.strip()
                remote_dev = curr.get("remote_device")
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
            return self._handle_arp(device)
        elif cmd == "route":
            return self._handle_legacy_route(device, parts)
        elif cmd == "ping":
            return self._handle_ping(device, parts)
        elif cmd == "curl":
            return self._handle_curl(device, parts)
        elif cmd in ("tracert", "traceroute"):

            return self._handle_tracert(device, parts)
        elif cmd in ("netstat", "ss"):
            return self._handle_netstat(device, parts)
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
            device._terminal_sessions.append({
                "state": "AWAITING_NANO_INPUT",
                "file": parts[1],
                "content": []
            })
            return f"--- NANO EDITOR: {parts[1]} ---\nType your text. Type ':wq' or 'EOF' on a new line to save and exit."
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
            output += "  ifconfig   - Configure a network interface\n"
            output += "  ip         - Show / manipulate routing, devices, policy routing and tunnels\n"
            output += "  arp        - (Legacy) Display the local ARP cache\n"
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
        elif topic == "route":
            return "Usage:\n  route\n  route add [dest_subnet] via [next_hop_ip]\n  route del [dest_subnet]"
        elif topic == "service":
            return "Usage:\n  service list\n  service add <name> <protocol> <port>\n  service start <name>\n  service stop <name>\n  service remove <name>"
        elif topic == "su":
            return "Usage: su [USER]\nChange user ID or become superuser.\nIf USER is not specified, it defaults to root."
        elif topic == "nano":
            return "Usage: nano [FILE]\nOpen the nano interactive text editor for FILE.\nType your text, then type ':wq' or 'EOF' on a new line to save and exit."
        elif topic == "update":
            return "Usage: update\nReload and apply system configurations from /etc/hostname and /etc/network/interfaces without a reboot."
        elif topic == "mount":
            return "Usage: mount [NAME]\nMount a new virtual drive under /mnt/[NAME]. Requires root."
        elif topic == "umount":
            return "Usage: umount [NAME]\nUnmount a virtual drive from /mnt/[NAME]. Requires root."
        elif topic == "keygen":
            return "Usage: keygen\nGenerates a TSIG key for secure DNS zone transfers."
        elif topic == "nslookup":
            return "Usage: nslookup [options] [name] [server]\nOptions:\n  -type=TYPE   Query for specific record type (A, CNAME, SRV, PTR, AXFR)"
        elif topic == "hostname":
            return "Usage: hostname\nPrints the name of the current system."
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
        else:
            return f"No manual entry for {topic}"


    # VFS Command Handlers
    def _handle_vfs_command(self, device, parts):
        cmd = parts[0]
        vfs = getattr(device, "vfs", None)
        if not vfs:
            return f"bash: {cmd}: File system not available on this device"
            
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
            show_hidden = "-a" in "".join(flags)
            
            target = vfs.curr_fol
            if args:
                target = vfs.get_item(args[0])
                if not target:
                    return f"ls: {args[0]} is a file or doesn't exist."
                
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
            item = vfs.get_item(name)
            from backend.database.fs import File
            if not isinstance(item, File):
                return f"cat: {name} is a folder or doesn't exist."
            if not check_permission(item, getattr(device, "current_user", "root"), 'r'):
                return f"cat: {name}: Permission denied"
                
            out = f"========{item.name}========\n"
            if item.contents:
                if isinstance(item.contents, list):
                    out += "\n".join(item.contents)
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
            if len(parts) < 2 or parts[1] == "~":
                vfs.curr_fol = vfs.tree
                return ""
            if parts[1] == "..":
                vfs.jmp_out()
                return ""
            if parts[1] == ".":
                return ""
                
            # Check execute permission before changing directory
            item = vfs.get_item(parts[1])
            if item:
                from backend.database.fs import Folder
                if isinstance(item, Folder) and not check_permission(item, getattr(device, "current_user", "root"), 'x'):
                    return f"bash: cd: {parts[1]}: Permission denied"
                    
            import io
            from contextlib import redirect_stdout
            f = io.StringIO()
            with redirect_stdout(f):
                vfs.jmp_into(parts[1])
            err = f.getvalue().strip()
            return err if err else ""

        elif cmd == "scp":
            if len(parts) < 3:
                return "usage: scp <source> <user@host:destination>"
            return "scp: transferring files to remote VFS requires active SSH daemon file handler (coming soon in Phase 3)"
            
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
                                if self.state_manager: self.state_manager.save()
                                return f"Added {ip_cidr} to {dev_name}."
                            except Exception as e:
                                return f"Error: invalid IP/CIDR '{ip_cidr}'"
                        else:
                            intf.ip = None
                            intf.subnet = None
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

    def _handle_arp(self, device):
        output = "ARP Cache:\n"
        has_arp = False
        for intf in getattr(device, "interfaces", []):
            if hasattr(intf, "arp") and intf.arp:
                has_arp = True
                for ip, mac in intf.arp.cache.items():
                    output += f"({intf.name}) {ip} -> {mac}\n"
        
        if not has_arp:
            return "ARP not supported on this device."
        elif output == "ARP Cache:\n":
            output += "(empty)\n"
        return output

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
        args = parts[1:]
        output = "Active Internet connections (w/o servers)\n"
        output += "Proto Recv-Q Send-Q Local Address           Foreign Address         State\n"
        
        has_sockets = False
        
        # Check if device has any ports open/listening
        if hasattr(device, "services"):
            for srv in device.services:
                if getattr(srv, "status", "").lower() == "running":
                    port = getattr(srv, "port", 0)
                    proto = getattr(srv, "protocol", "tcp").lower()
                    local = f"0.0.0.0:{port}"
                    output += f"{proto:<5} 0      0      {local:<23} 0.0.0.0:*               LISTEN\n"
                    has_sockets = True
                    
        if not has_sockets:
            output = "Active Internet connections (w/o servers)\nProto Recv-Q Send-Q Local Address           Foreign Address         State\n(No active sockets found)"
            
        return output

    def _handle_echo(self, device, parts):
        if len(parts) < 2:
            return "Usage: echo [-p port] [-t tcp|udp] destination [message]"

        port = 7
        proto = "TCP"
        target_ip = None
        message_parts = []

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
            return "Usage: echo [-p port] [-t tcp|udp] destination [message]"

        message = " ".join(message_parts) if message_parts else "CyberHazardLab Echo Probe"

        if not device or not getattr(device, "interfaces", []):
            return "Device has no network interfaces configured."

        intf = device.interfaces[0]
        if not intf.ip or intf.ip == "0.0.0.0":
            return "Device has no valid IP assigned."

        network = getattr(device, "network", None)
        if not network:
            return "Device is not connected to a network."

        # Resolve destination if hostname given
        dest_node = network.get_host_by_ip(target_ip)
        if not dest_node:
            dest_node = network.get_host(target_ip)
            if dest_node and getattr(dest_node, "interfaces", []):
                target_ip = dest_node.interfaces[0].ip
            else:
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
            
        else:
            return "Usage: service {list|add|start|stop|remove}"

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
                
        if not dns_ip:
            for s in getattr(device, "services", []):
                if s.name.upper() in ("DNS_CLIENT", "DNS") and s.status.lower() == "running":
                    dns_ip = s.config.get("dns_server")
                    break
        
        if not dns_ip:
            dns_ip = "8.8.8.8"
            
        dns_ip = dns_ip.strip()
        
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
        
        return f"Unmounted /mnt/{name}"
