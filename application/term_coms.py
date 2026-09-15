import ipaddress
import traceback

class TerminalCommandHandler:
    def __init__(self, sim, ncm, state_manager):
        self.sim = sim
        self.ncm = ncm
        self.state_manager = state_manager
        
    def execute(self, device, command_str):
        parts = command_str.split()
        if not parts:
            return ""
            
        cmd = parts[0]
        
        if cmd == "help":
            return self._handle_help(parts)
        elif cmd == "hostname":
            return device.name
        elif cmd == "ip":
            return self._handle_ip(device, parts)
        elif cmd == "arp":
            return self._handle_arp(device)
        elif cmd == "route":
            return self._handle_legacy_route(device, parts)
        elif cmd == "ping":
            return self._handle_ping(device, parts)
        elif cmd in ("tracert", "traceroute"):
            return self._handle_tracert(device, parts)
        elif cmd in ("netstat", "ss"):
            return self._handle_netstat(device, parts)
        elif cmd == "ifconfig":
            # Just an alias mapping for our ip addr logic
            parts = ["ip", "addr", "show"]
            return self._handle_ip(device, parts)
        else:
            return f"Nox OS > Command '{cmd}' not recognized."
            
    def _handle_help(self, parts):
        if len(parts) == 1:
            output = "NOX OS TERMINAL COMMANDS:\n"
            output += "  help       - Show this help message (use 'help [command]' for more info)\n"
            output += "  ping       - Send ICMP ECHO_REQUEST packets\n"
            output += "  tracert    - Trace route to a remote host\n"
            output += "  netstat    - Print network connections and routing tables\n"
            output += "  ifconfig   - Configure a network interface\n"
            output += "  ip         - Show / manipulate routing, devices, policy routing and tunnels\n"
            output += "  arp        - (Legacy) Display the local ARP cache\n"
            output += "  route      - (Legacy) Display the routing table\n"
            output += "  hostname   - Show current system hostname"
            return output
            
        topic = parts[1]
        
        if topic == "ping":
            return "Usage: ping [target_ip]\nSends ICMP ECHO_REQUEST packets to network hosts."
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
        elif topic == "hostname":
            return "Usage: hostname\nPrints the name of the current system."
        elif topic == "ip":
            if len(parts) == 2:
                output = "Usage: ip [ OPTIONS ] OBJECT { COMMAND | help }\n"
                output += "OBJECT := { link | addr | route | neigh | maddr }\n"
                output += "Use 'help ip [object]' for detailed information."
                return output
                
            sub_topic = parts[2]
            if sub_topic == "link":
                return "ip link - network device configuration\n  show             - display all interfaces\n  set [dev] up     - enable interface\n  set [dev] down   - disable interface"
            elif sub_topic == "addr":
                return "ip addr - protocol address management\n  show                                - list IP addresses\n  add [ip/cidr] dev [name]            - assign IP address to interface\n  del [ip/cidr] dev [name]            - remove IP address from interface"
            elif sub_topic == "route":
                return "ip route - routing table management\n  show                                - list routes\n  add [cidr] via [ip] dev [name]      - add static route\n  del [cidr]                          - delete static route\n  get [ip]                            - show path to destination\n  flush                               - clear routing table"
            elif sub_topic == "neigh":
                return "ip neigh - neighbour/ARP table management\n  show             - list ARP entries\n  flush            - clear ARP cache"
            elif sub_topic == "maddr":
                return "ip maddr - multicast address management"
            else:
                return f"Unknown ip object '{sub_topic}'"
        else:
            return f"No manual entry for {topic}"

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
                intf = self.ncm.get_interface(device.name, dev_name)
                if intf:
                    intf.status = "up" if state == "up" else "down"
                    self.state_manager.save()
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
                    intf = self.ncm.get_interface(device.name, dev_name)
                    if not intf:
                        return f"Cannot find device \"{dev_name}\""
                    else:
                        if action == "add":
                            try:
                                net = ipaddress.IPv4Interface(ip_cidr)
                                intf.ip = str(net.ip)
                                intf.subnet = str(net.network)
                                self.state_manager.save()
                                return f"Added {ip_cidr} to {dev_name}."
                            except Exception as e:
                                return f"Error: invalid IP/CIDR '{ip_cidr}'"
                        else:
                            intf.ip = None
                            intf.subnet = None
                            self.state_manager.save()
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
                        self.state_manager.save()
                        return f"Route added: {dest_subnet} via {next_hop or 'DIRECT'} dev {out_intf.name}"
                    else:
                        return "Error: Network unreachable or invalid device"
                elif len(parts) >= 4 and parts[2] == "del":
                    dest_subnet = parts[3]
                    device.routes = [r for r in device.routes if str(r['destination']) != dest_subnet]
                    self.state_manager.save()
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
                    self.state_manager.save()
                    return "Flushed routing table."
                else:
                    return "Usage: ip route { show | add | del | get | flush }"
                    
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
                
                intf = self.ncm.get_interface(device.name, dev_name)
                if not intf or not hasattr(intf, "arp") or not intf.arp:
                    return f"Cannot find device \"{dev_name}\" or ARP not supported."
                
                if action == "add":
                    intf.arp.cache[target_ip] = mac
                    self.state_manager.save()
                    return f"Added {target_ip} at {mac} to {dev_name} ARP cache."
                else:
                    if target_ip in intf.arp.cache:
                        del intf.arp.cache[target_ip]
                        self.state_manager.save()
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
                    self.state_manager.save()
                    return f"Route added: {dest_subnet} via {next_hop} (dev {out_intf.name})"
                else:
                    return f"Network unreachable: Cannot reach next hop {next_hop}"
            elif len(parts) == 3 and parts[1] == "del":
                dest_subnet = parts[2]
                device.routes = [r for r in device.routes if str(r['destination']) != dest_subnet]
                self.state_manager.save()
                return f"Route deleted: {dest_subnet}"
            else:
                return "Usage:\n  route\n  route add [dest_subnet] via [next_hop_ip]\n  route del [dest_subnet]"

    def _handle_ping(self, device, parts):
        if len(parts) < 2:
            return "Usage: ping [target_ip]"
        else:
            target_ip = parts[1]
            if not device:
                return "Cannot run ping from this device."
            
            output = f"PING {target_ip} ({target_ip}) 56(84) bytes of data.\n"
            success_count = 0
            
            try:
                for i in range(4):
                    result = self.sim.ping(device, target_ip)
                    if result:
                        if isinstance(result, dict):
                            rtype = result.get("type")
                            rsource = result.get("source", "Unknown")
                            if rtype == "TIME_EXCEEDED":
                                output += f"From {rsource} icmp_seq={i+1} Time to live exceeded\n"
                            elif rtype == "DESTINATION_UNREACHABLE":
                                output += f"From {rsource} icmp_seq={i+1} Destination Host Unreachable\n"
                            elif rtype == "TIMEOUT":
                                output += f"From {target_ip} icmp_seq={i+1} Request timed out\n"
                            else:
                                ttl = result.get('ttl', 64)
                                output += f"64 bytes from {rsource}: icmp_seq={i+1} ttl={ttl} time=1 ms\n"
                                success_count += 1
                        else:
                            # Fallback for simple truthy
                            output += f"64 bytes from {target_ip}: icmp_seq={i+1} ttl=64 time=1 ms\n"
                            success_count += 1
                    else:
                        output += f"From {target_ip} icmp_seq={i+1} Request timed out\n"
                
                output += f"\n--- {target_ip} ping statistics ---\n"
                output += f"4 packets transmitted, {success_count} received, {100 - (success_count/4*100):.0f}% packet loss, time 3003ms"
                return output
            except Exception as e:
                return f"Ping failed: {str(e)}\n{traceback.format_exc()}"

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
            
        output = f"Tracing route to {target_ip} over a maximum of {max_hops} hops:\n\n"
        
        if not hasattr(self.sim, "traceroute"):
            return "Traceroute is not implemented on the simulation engine."
            
        try:
            hops = self.sim.traceroute(device, target_ip, max_hops=max_hops)
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
        # Dummy netstat based on active tcp/udp services if we have them
        # Nox OS currently doesn't simulate full socket layer, but we can list active services if any
        output = "Active Internet connections (w/o servers)\n"
        output += "Proto Recv-Q Send-Q Local Address           Foreign Address         State\n"
        
        has_sockets = False
        
        # Check if device has any ports open/listening
        if hasattr(device, "services"):
            for srv_name, srv in device.services.items():
                if getattr(srv, "is_running", False):
                    port = getattr(srv, "port", 0)
                    proto = getattr(srv, "protocol", "tcp")
                    local = f"0.0.0.0:{port}"
                    output += f"{proto:<5} 0      0      {local:<23} 0.0.0.0:*               LISTEN\n"
                    has_sockets = True
                    
        if not has_sockets:
            output = "Active Internet connections (w/o servers)\nProto Recv-Q Send-Q Local Address           Foreign Address         State\n(No active sockets found)"
            
        return output
