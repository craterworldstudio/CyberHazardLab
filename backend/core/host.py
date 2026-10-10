from backend.database.fs import FileSystem
from backend.core.node import Node
from backend.core.device import DeviceType
from backend.core.interface import NetworkInterface
from backend.core.mac import generate_mac

class Host(Node):
    def __init__(self, name: str, device_type: DeviceType = DeviceType.PC, network=None):
        super().__init__(name=name, device_type=device_type, network=network)
        self.forwarding_enabled = False
        self.vfs = FileSystem()
        self.log_cache = []
        self.current_user = "user"
        self.users = {"root": "toor", "user": "user"}
        self.groups = {
            "root": {"gid": 0, "members": ["root"]},
            "daemon": {"gid": 1, "members": []},
            "bin": {"gid": 2, "members": []},
            "sys": {"gid": 3, "members": []},
            "adm": {"gid": 4, "members": ["user"]},
            "sudo": {"gid": 27, "members": ["user"]},
            "users": {"gid": 100, "members": []},
            "user": {"gid": 1000, "members": ["user"]}
        }
        self.user_accounts = {
            "root": {
                "uid": 0,
                "gid": 0,
                "gecos": "root",
                "home": "/root",
                "shell": "/bin/bash",
                "password": "toor",
                "groups": ["root"]
            },
            "user": {
                "uid": 1000,
                "gid": 1000,
                "gecos": "Standard User",
                "home": "/home/user",
                "shell": "/bin/bash",
                "password": "user",
                "groups": ["user", "sudo", "adm"]
            }
        }
        
        # Default interface eth0
        self.add_interface(NetworkInterface(
            name="eth0",
            mac=generate_mac(),
            ip="0.0.0.0",
            subnet="0.0.0.0/0",
            owner=self
        ))
        
        self._generate_system_files()

    @property
    def ip_forwarding(self):
        return getattr(self, "forwarding_enabled", False)

    @ip_forwarding.setter
    def ip_forwarding(self, val):
        self.forwarding_enabled = bool(val)
        self._sync_ip_forward_proc()

    def _sync_ip_forward_proc(self):
        vfs = getattr(self, "vfs", None)
        if not vfs:
            return
        f = vfs.path_to_tree("/proc/sys/net/ipv4/ip_forward")
        val = "1\n" if getattr(self, "forwarding_enabled", False) else "0\n"
        if f:
            f.contents = val
        else:
            self._ensure_proc_ip_forward()

    def _ensure_proc_ip_forward(self):
        vfs = getattr(self, "vfs", None)
        if not vfs:
            return
        from backend.database.fs import Folder, File
        proc = vfs.get_item("proc") or vfs.path_to_tree("/proc")
        if not proc:
            proc = Folder("proc", parent=vfs.tree)
            proc.path = "/proc"
            vfs.tree.add(proc)
        
        sys_fol = None
        for itm in proc.all:
            if itm.name == "sys":
                sys_fol = itm
                break
        if not sys_fol:
            sys_fol = Folder("sys", parent=proc)
            sys_fol.path = "/proc/sys"
            proc.add(sys_fol)

        net_fol = None
        for itm in sys_fol.all:
            if itm.name == "net":
                net_fol = itm
                break
        if not net_fol:
            net_fol = Folder("net", parent=sys_fol)
            net_fol.path = "/proc/sys/net"
            sys_fol.add(net_fol)

        ipv4_fol = None
        for itm in net_fol.all:
            if itm.name == "ipv4":
                ipv4_fol = itm
                break
        if not ipv4_fol:
            ipv4_fol = Folder("ipv4", parent=net_fol)
            ipv4_fol.path = "/proc/sys/net/ipv4"
            net_fol.add(ipv4_fol)

        ip_fwd_file = None
        for itm in ipv4_fol.all:
            if itm.name == "ip_forward":
                ip_fwd_file = itm
                break
        if not ip_fwd_file:
            ip_fwd_file = File("ip_forward")
            ip_fwd_file.perms = "rw-rw-rw-"
            ip_fwd_file.set_path(ipv4_fol.path)
            ipv4_fol.add(ip_fwd_file)
        else:
            ip_fwd_file.perms = "rw-rw-rw-"
        ip_fwd_file.contents = "1\n" if getattr(self, "forwarding_enabled", False) else "0\n"
        
    def _generate_system_files(self):
        vfs = self.vfs
        orig_fol = getattr(vfs, "curr_fol", None)
        from backend.database.fs import Folder, File
        
        # Ensure /etc exists
        vfs.curr_fol = vfs.tree
        etc = vfs.get_item("etc")
        if not etc:
            etc = Folder("etc")
            etc.perms = "rwxr-xr-x"
            etc.parent = vfs.tree
            etc.path = "/etc"
            vfs.tree.add(etc)
        else:
            etc.perms = "rwxr-xr-x"
            
        # /etc/hostname
        vfs.curr_fol = etc
        hostname_file = vfs.get_item("hostname")
        if not hostname_file:
            hostname_file = File("hostname")
            hostname_file.set_path(etc.path)
            etc.add(hostname_file)
        hostname_file.contents = self.name
        
        # Ensure /etc/network exists
        network = vfs.get_item("network")
        if not network:
            network = Folder("network")
            network.parent = etc
            network.path = "/etc/network"
            etc.add(network)
            
        # /etc/network/interfaces
        vfs.curr_fol = network
        interfaces_file = vfs.get_item("interfaces")
        if not interfaces_file:
            interfaces_file = File("interfaces")
            interfaces_file.set_path(network.path)
            network.add(interfaces_file)
            
        iface = self.interfaces[0] if self.interfaces else None
        if iface:
            is_dhcp = getattr(self, "dhcp_enabled", False) or any(getattr(s, "name", "") == "DHCP_CLIENT" for s in getattr(self, "services", []))
            method = "dhcp" if is_dhcp else "static"
            
            # Format netmask cleanly
            netmask = "255.255.255.0"
            if iface.subnet and "/" in iface.subnet:
                try:
                    import ipaddress
                    netmask = str(ipaddress.IPv4Network(iface.subnet, strict=False).netmask)
                except Exception:
                    netmask = iface.subnet.split('/')[1]
                    
            lines = [
                f"auto {iface.name}",
                f"iface {iface.name} inet {method}",
                f"  address {iface.ip}",
                f"  netmask {netmask}",
                f"  mac {iface.mac}"
            ]
            gw = getattr(iface, "gateway", None) or getattr(self, "default_gateway", None)
            if gw:
                lines.append(f"  gateway {gw}")
            dns_val = getattr(self, "dns_server", None)
            if dns_val:
                lines.append(f"  dns-nameservers {dns_val}")
            interfaces_file.contents = "\n".join(lines)
            
        # /etc/resolv.conf
        vfs.curr_fol = etc
        resolv_file = vfs.get_item("resolv.conf")
        if not resolv_file:
            resolv_file = File("resolv.conf")
            resolv_file.set_path(etc.path)
            etc.add(resolv_file)
        dns_ip = getattr(self, "dns_server", None) or "8.8.8.8"
        resolv_file.contents = f"# Generated by Cyber Hazard Lab DHCP / Network\nnameserver {dns_ip}\n"

        # Ensure /mnt exists
        vfs.curr_fol = vfs.tree
        mnt = vfs.get_item("mnt")
        if not mnt:
            mnt = Folder("mnt")
            mnt.perms = "rwxr-xr-x"
            mnt.parent = vfs.tree
            mnt.path = "/mnt"
            vfs.tree.add(mnt)
        else:
            mnt.perms = "rwxr-xr-x"
            
        # Populate drives under /mnt
        vfs.curr_fol = mnt
        from backend.database.fs import Drive, Folder
        from backend.core.device import DeviceType

        is_nas = self.device_type == DeviceType.NAS
        has_dns = any(getattr(s, "name", "").upper() in ("DNS", "DNS_SERVER") for s in getattr(self, "services", [])) or "dns" in self.name.lower()
        has_ad = any(getattr(s, "name", "").upper() in ("AD", "KERBEROS", "LDAP") for s in getattr(self, "services", [])) or "dc" in self.name.lower()

        # Mount public drives (D and E) only if NAS
        if is_nas:
            if not mnt.get_item("D"):
                d_drive = Drive("D", owner="root", group="root", perms="rwxr-xr-x")
                d_drive.parent = mnt
                d_drive.path = "/mnt/D"
                mnt.add(d_drive)
            if not mnt.get_item("E"):
                e_drive = Drive("E", owner="root", group="root", perms="rwxr-xr-x")
                e_drive.parent = mnt
                e_drive.path = "/mnt/E"
                mnt.add(e_drive)
        elif not getattr(self, "_cleaned_stale_mounts", False):
            self._cleaned_stale_mounts = True
            for d_name in ("D", "E"):
                item = mnt.get_item(d_name)
                if item:
                    if item in mnt.all: mnt.all.remove(item)
                    if item in mnt.visible: mnt.visible.remove(item)
                    if item in mnt.hidden: mnt.hidden.remove(item)

        # Mount hidden drive (.dns_storage) only if host has DNS server
        if has_dns:
            if not mnt.get_item(".dns_storage"):
                dns_drive = Drive(".dns_storage", hidden=True, owner="root", group="root", perms="rwx------")
                dns_drive.parent = mnt
                dns_drive.path = "/mnt/.dns_storage"
                z_file = File("named.zones")
                z_file.owner = "root"
                z_file.group = "root"
                z_file.perms = "rw-------"
                z_file.contents = "// BIND9 Secure Zone Database\nzone \"local\" { type master; file \"/mnt/.dns_storage/db.local\"; };\n"
                dns_drive.add(z_file)
                mnt.add(dns_drive, h=True)
        else:
            item = mnt.get_item(".dns_storage")
            if item:
                if item in mnt.all: mnt.all.remove(item)
                if item in mnt.visible: mnt.visible.remove(item)
                if item in mnt.hidden: mnt.hidden.remove(item)

        # Mount hidden drive (.ad_database) only if host has AD server
        if has_ad:
            if not mnt.get_item(".ad_database"):
                ad_drive = Drive(".ad_database", hidden=True, owner="root", group="root", perms="rwx------")
                ad_drive.parent = mnt
                ad_drive.path = "/mnt/.ad_database"
                dit_file = File("ntds", "dit")
                dit_file.owner = "root"
                dit_file.group = "root"
                dit_file.perms = "rw-------"
                dit_file.contents = "[ACTIVE_DIRECTORY_DATABASE_SCHEMA_V1]\n"
                ad_drive.add(dit_file)
                mnt.add(ad_drive, h=True)
        else:
            item = mnt.get_item(".ad_database")
            if item:
                if item in mnt.all: mnt.all.remove(item)
                if item in mnt.visible: mnt.visible.remove(item)
                if item in mnt.hidden: mnt.hidden.remove(item)

        # Generate /mnt/.mounts and /mnt/mounts.tab dynamically based on actual mounted drives
        mount_lines = [
            "# Cyber Hazard Lab Virtual File System Mount Table",
            f"# {'DEVICE':<16} {'MOUNTPOINT':<20} {'TYPE':<8} {'PERMS':<10} {'VISIBILITY':<10} DESCRIPTION",
            f"  {'/dev/root':<16} {'/':<20} {'ext4':<8} {'rw-rwxr--':<10} {'public':<10} System Root Drive (C:)"
        ]
        if mnt.get_item("D"):
            dev_name = "/dev/storage0" if is_nas else "/dev/D"
            desc = "Secondary Storage Pool D" if is_nas else "Mounted Volume D"
            mount_lines.append(f"  {dev_name:<16} {'/mnt/D':<20} {'ext4':<8} {'rwxr-xr-x':<10} {'public':<10} {desc}")
        if mnt.get_item("E"):
            dev_name = "/dev/storage1" if is_nas else "/dev/E"
            desc = "Backup Storage Pool E" if is_nas else "Mounted Volume E"
            mount_lines.append(f"  {dev_name:<16} {'/mnt/E':<20} {'ext4':<8} {'rwxr-xr-x':<10} {'public':<10} {desc}")
        if has_dns and mnt.get_item(".dns_storage"):
            mount_lines.append(f"  {'/dev/dns_zone':<16} {'/mnt/.dns_storage':<20} {'iscsi':<8} {'rwx------':<10} {'hidden':<10} BIND9 Zone Secure Storage (Root Only)")
        if has_ad and mnt.get_item(".ad_database"):
            mount_lines.append(f"  {'/dev/ntds_dit':<16} {'/mnt/.ad_database':<20} {'iscsi':<8} {'rwx------':<10} {'hidden':<10} Active Directory NTDS Database (Root Only)")

        for item in mnt.all:
            if item is mnt or item is mnt.parent: continue
            if getattr(item, "name", "") in ("mounts", "mounts.tab", ".mounts", "D", "E", ".dns_storage", ".ad_database"): continue
            if isinstance(item, (Drive, Folder)):
                is_h = getattr(item, "is_hidden", False) or item.name.startswith(".")
                vis = "hidden" if is_h else "public"
                mount_lines.append(f"  {'/dev/' + item.name:<16} {'/mnt/' + item.name:<20} {'ext4':<8} {item.perms:<10} {vis:<10} Mounted Volume {item.name}")

        mount_content = "\n".join(mount_lines) + "\n"
        
        # /mnt/mounts.tab (visible)
        mtab = mnt.get_item("mounts.tab")
        if not mtab:
            mtab = File("mounts", "tab")
            mtab.set_path(mnt.path)
            mnt.add(mtab)
        mtab.contents = mount_content

        # /mnt/.mounts (hidden)
        dot_mounts = mnt.get_item(".mounts")
        if not dot_mounts:
            dot_mounts = File(".mounts")
            dot_mounts.set_path(mnt.path)
            mnt.add(dot_mounts, h=True)
        dot_mounts.contents = mount_content

        # Ensure /var and /var/log exist
        vfs.curr_fol = vfs.tree
        var = vfs.get_item("var")
        if not var:
            var = Folder("var")
            var.perms = "rwxr-xr-x"
            var.parent = vfs.tree
            var.path = "/var"
            vfs.tree.add(var)
        else:
            var.perms = "rwxr-xr-x"

        vfs.curr_fol = var
        log_fol = vfs.get_item("log")
        if not log_fol:
            log_fol = Folder("log")
            log_fol.parent = var
            log_fol.path = "/var/log"
            var.add(log_fol)

        vfs.curr_fol = log_fol
        syslog = log_fol.get_item("syslog")
        if not syslog:
            syslog = File("syslog")
            syslog.set_path(log_fol.path)
            syslog.contents = f"systemd[1]: Started Cyber Hazard Lab OS on {self.name}.\n"
            log_fol.add(syslog)

        auth_log = log_fol.get_item("auth.log")
        if not auth_log:
            auth_log = File("auth", "log")
            auth_log.set_path(log_fol.path)
            auth_log.contents = f"systemd-logind[1]: New session created for user root.\n"
            log_fol.add(auth_log)

        # Synchronize local accounts, VFS account files, and home directories
        self._sync_account_files()
        
        self._ensure_proc_ip_forward()
        
        if orig_fol:
            vfs.curr_fol = orig_fol
        else:
            vfs.curr_fol = vfs.tree

    def _sync_account_files(self):
        vfs = getattr(self, "vfs", None)
        if not vfs:
            return
        from backend.database.fs import Folder, File
        orig_fol = getattr(vfs, "curr_fol", None)
        
        # Ensure /etc exists
        etc = vfs.get_item("etc") or vfs.path_to_tree("/etc")
        if not etc:
            etc = Folder("etc")
            etc.perms = "rwxr-xr-x"
            etc.owner = "root"
            etc.group = "root"
            etc.parent = vfs.tree
            etc.path = "/etc"
            vfs.tree.add(etc)

        # 1. /etc/passwd
        passwd_lines = [
            "root:x:0:0:root:/root:/bin/bash",
            "daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin",
            "bin:x:2:2:bin:/bin:/usr/sbin/nologin",
            "sys:x:3:3:sys:/dev:/usr/sbin/nologin",
            "sync:x:4:65534:sync:/bin:/bin/sync"
        ]
        for uname, udata in getattr(self, "user_accounts", {}).items():
            if uname == "root":
                continue
            uid = udata.get("uid", 1000)
            gid = udata.get("gid", 1000)
            gecos = udata.get("gecos", uname)
            home = udata.get("home", f"/home/{uname}")
            shell = udata.get("shell", "/bin/bash")
            passwd_lines.append(f"{uname}:x:{uid}:{gid}:{gecos}:{home}:{shell}")
        passwd_file = etc.get_item("passwd")
        if not passwd_file:
            passwd_file = File("passwd")
            passwd_file.set_path(etc.path)
            etc.add(passwd_file)
        passwd_file.owner = "root"
        passwd_file.group = "root"
        passwd_file.perms = "rw-r--r--"
        passwd_file.contents = "\n".join(passwd_lines) + "\n"

        # 2. /etc/shadow (root-only access, 600)
        shadow_lines = []
        for uname, udata in getattr(self, "user_accounts", {}).items():
            pw = udata.get("password", "")
            h_str = f"$6$chl${(hash(uname + pw) & 0xffffffff):08x}" if pw else "*"
            shadow_lines.append(f"{uname}:{h_str}:19700:0:99999:7:::")
        for sys_u in ("daemon", "bin", "sys", "sync"):
            shadow_lines.append(f"{sys_u}:*:19700:0:99999:7:::")
        shadow_file = etc.get_item("shadow")
        if not shadow_file:
            shadow_file = File("shadow")
            shadow_file.set_path(etc.path)
            etc.add(shadow_file)
        shadow_file.owner = "root"
        shadow_file.group = "root"
        shadow_file.perms = "rw-------"
        shadow_file.contents = "\n".join(shadow_lines) + "\n"

        # 3. /etc/group
        group_lines = []
        for gname, gdata in getattr(self, "groups", {}).items():
            gid = gdata.get("gid", 1000)
            members = ",".join(gdata.get("members", []))
            group_lines.append(f"{gname}:x:{gid}:{members}")
        group_file = etc.get_item("group")
        if not group_file:
            group_file = File("group")
            group_file.set_path(etc.path)
            etc.add(group_file)
        group_file.owner = "root"
        group_file.group = "root"
        group_file.perms = "rw-r--r--"
        group_file.contents = "\n".join(group_lines) + "\n"

        # 4. /etc/sudoers (root-only read, 440)
        sudoers_file = etc.get_item("sudoers")
        if not sudoers_file:
            sudoers_file = File("sudoers")
            sudoers_file.set_path(etc.path)
            etc.add(sudoers_file)
        sudoers_file.owner = "root"
        sudoers_file.group = "root"
        sudoers_file.perms = "r--r-----"
        sudoers_file.contents = (
            "# /etc/sudoers\n"
            "Defaults\tenv_reset\n"
            "Defaults\tmail_badpass\n"
            "Defaults\tsecure_path=\"/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\"\n\n"
            "root\tALL=(ALL:ALL) ALL\n"
            "%sudo\tALL=(ALL:ALL) ALL\n"
        )

        # 5. /home and /root directories
        home = vfs.get_item("home") or vfs.path_to_tree("/home")
        if not home:
            home = Folder("home")
            home.perms = "rwxr-xr-x"
            home.owner = "root"
            home.group = "root"
            home.parent = vfs.tree
            home.path = "/home"
            vfs.tree.add(home)

        root_fol = vfs.get_item("root") or vfs.path_to_tree("/root")
        if not root_fol:
            root_fol = Folder("root")
            root_fol.owner = "root"
            root_fol.group = "root"
            root_fol.perms = "rwx------"
            root_fol.parent = vfs.tree
            root_fol.path = "/root"
            vfs.tree.add(root_fol)

        for uname, udata in getattr(self, "user_accounts", {}).items():
            if uname == "root":
                continue
            h_path = udata.get("home", f"/home/{uname}")
            if h_path.startswith("/home/"):
                subname = h_path.replace("/home/", "").strip("/")
                ufol = home.get_item(subname)
                prim_gid = udata.get("gid", 1000)
                prim_gname = next((gn for gn, gd in getattr(self, "groups", {}).items() if gd.get("gid") == prim_gid), uname)
                if not ufol:
                    ufol = Folder(subname)
                    ufol.owner = uname
                    ufol.group = prim_gname
                    ufol.perms = "rwxr-xr-x"
                    ufol.parent = home
                    ufol.path = f"/home/{subname}"
                    home.add(ufol)
                else:
                    ufol.owner = uname
                    ufol.group = prim_gname

        if orig_fol:
            vfs.curr_fol = orig_fol

    def add_user(self, username, password="password", uid=None, gid=None, gecos=None, home=None, shell="/bin/bash", groups=None, create_home=True):
        if username in self.user_accounts:
            raise ValueError(f"User '{username}' already exists")
        
        # Determine UID
        if uid is None:
            max_uid = max([u.get("uid", 1000) for u in self.user_accounts.values()] or [999])
            uid = max(1000, max_uid + 1)
            
        # Primary group
        if gid is None:
            if username not in self.groups:
                self.groups[username] = {"gid": uid, "members": [username]}
                gid = uid
            else:
                gid = self.groups[username]["gid"]
        else:
            gname = next((gn for gn, gd in self.groups.items() if gd.get("gid") == gid), None)
            if not gname:
                self.groups[username] = {"gid": gid, "members": [username]}
            elif username not in self.groups[gname]["members"]:
                self.groups[gname]["members"].append(username)
                
        supp_groups = list(groups or [])
        for sg in supp_groups:
            if sg in self.groups:
                if username not in self.groups[sg]["members"]:
                    self.groups[sg]["members"].append(username)
            else:
                max_gid = max([g.get("gid", 1000) for g in self.groups.values()] or [999])
                self.groups[sg] = {"gid": max(1000, max_gid + 1), "members": [username]}
                
        user_groups_list = [next((gn for gn, gd in self.groups.items() if gd.get("gid") == gid), username)]
        for sg in supp_groups:
            if sg not in user_groups_list:
                user_groups_list.append(sg)
                
        self.user_accounts[username] = {
            "uid": uid,
            "gid": gid,
            "gecos": gecos or username,
            "home": home or f"/home/{username}",
            "shell": shell,
            "password": password,
            "groups": user_groups_list
        }
        self.users[username] = password
        self._sync_account_files()
        return self.user_accounts[username]

    def delete_user(self, username, remove_home=False):
        if username not in self.user_accounts:
            raise ValueError(f"User '{username}' does not exist")
        if username == "root":
            raise ValueError("Cannot delete root user")
            
        u_info = self.user_accounts.pop(username)
        if username in self.users:
            del self.users[username]
            
        for gname, gdata in self.groups.items():
            if username in gdata.get("members", []):
                gdata["members"].remove(username)
                
        if username in self.groups and not self.groups[username].get("members"):
            del self.groups[username]
            
        if remove_home and self.vfs:
            h_path = u_info.get("home", f"/home/{username}")
            h_item = self.vfs.path_to_tree(h_path)
            if h_item and getattr(h_item, "parent", None):
                h_item.parent.remove(h_item)
                
        self._sync_account_files()
        return True

    def modify_user(self, username, **kwargs):
        if username not in self.user_accounts:
            raise ValueError(f"User '{username}' does not exist")
        acc = self.user_accounts[username]
        if "password" in kwargs:
            acc["password"] = kwargs["password"]
            self.users[username] = kwargs["password"]
        if "shell" in kwargs:
            acc["shell"] = kwargs["shell"]
        if "gecos" in kwargs:
            acc["gecos"] = kwargs["gecos"]
        if "home" in kwargs:
            acc["home"] = kwargs["home"]
        if "gid" in kwargs:
            acc["gid"] = int(kwargs["gid"])
        if "append_groups" in kwargs:
            for g in kwargs["append_groups"]:
                if g in self.groups:
                    if username not in self.groups[g]["members"]:
                        self.groups[g]["members"].append(username)
                else:
                    max_gid = max([gd.get("gid", 1000) for gd in self.groups.values()] or [999])
                    self.groups[g] = {"gid": max(1000, max_gid + 1), "members": [username]}
                if g not in acc.get("groups", []):
                    acc.setdefault("groups", []).append(g)
        if "groups" in kwargs:
            new_groups = list(kwargs["groups"])
            prim_gname = next((gn for gn, gd in self.groups.items() if gd.get("gid") == acc["gid"]), None)
            for gname, gdata in self.groups.items():
                if gname != prim_gname and username in gdata.get("members", []):
                    gdata["members"].remove(username)
            for g in new_groups:
                if g in self.groups:
                    if username not in self.groups[g]["members"]:
                        self.groups[g]["members"].append(username)
                else:
                    max_gid = max([gd.get("gid", 1000) for gd in self.groups.values()] or [999])
                    self.groups[g] = {"gid": max(1000, max_gid + 1), "members": [username]}
            acc["groups"] = ([prim_gname] if prim_gname else []) + [g for g in new_groups if g != prim_gname]
        self._sync_account_files()
        return acc

    def set_password(self, username, new_password):
        if username not in self.user_accounts:
            raise ValueError(f"User '{username}' does not exist")
        self.user_accounts[username]["password"] = new_password
        self.users[username] = new_password
        self._sync_account_files()

    def add_group(self, group_name, gid=None):
        if group_name in self.groups:
            raise ValueError(f"Group '{group_name}' already exists")
        if gid is None:
            max_gid = max([g.get("gid", 1000) for g in self.groups.values()] or [999])
            gid = max(1000, max_gid + 1)
        self.groups[group_name] = {"gid": gid, "members": []}
        self._sync_account_files()
        return self.groups[group_name]

    def delete_group(self, group_name):
        if group_name not in self.groups:
            raise ValueError(f"Group '{group_name}' does not exist")
        if group_name in ("root", "sudo"):
            raise ValueError(f"Cannot delete system group '{group_name}'")
        g_gid = self.groups[group_name]["gid"]
        for uname, udata in self.user_accounts.items():
            if udata.get("gid") == g_gid:
                raise ValueError(f"Cannot remove group '{group_name}': it is the primary group of user '{uname}'")
        del self.groups[group_name]
        for uname, udata in self.user_accounts.items():
            if group_name in udata.get("groups", []):
                udata["groups"].remove(group_name)
        self._sync_account_files()
        return True

    def get_user_groups(self, username):
        if username not in self.user_accounts:
            return []
        groups = []
        for gname, gdata in self.groups.items():
            if username in gdata.get("members", []):
                groups.append(gname)
        prim_gid = self.user_accounts[username].get("gid")
        prim_gname = next((gn for gn, gd in self.groups.items() if gd.get("gid") == prim_gid), None)
        if prim_gname and prim_gname not in groups:
            groups.insert(0, prim_gname)
        return groups

    def log_event(self, event):
        """Records an event locally into host log cache and VFS /var/log files."""
        self.log_cache.append(event)
        vfs = getattr(self, "vfs", None)
        if not vfs:
            return
            
        import time
        t_str = time.strftime("%b %d %H:%M:%S")
        ev_type = getattr(event, "type", "EVENT")
        ev_src = getattr(event, "source", self.name)
        ev_dst = getattr(event, "destination", "")
        ev_sev = getattr(event, "severity", "INFO")
        ev_meta = getattr(event, "metadata", {}) or {}
        
        line = f"{t_str} {self.name.lower()} chl[{ev_sev}]: [{ev_type}] from={ev_src} to={ev_dst} {ev_meta}\n"
        
        syslog_file = vfs.path_to_tree("/var/log/syslog")
        if syslog_file and hasattr(syslog_file, "contents"):
            syslog_file.contents = (str(syslog_file.contents) or "") + line
            
        if any(k in ev_type for k in ("AUTH", "LOGIN", "SSH", "SU", "REVERSE_SHELL", "ARP_SPOOF", "PORT_SCAN")):
            auth_file = vfs.path_to_tree("/var/log/auth.log")
            if auth_file and hasattr(auth_file, "contents"):
                auth_file.contents = (str(auth_file.contents) or "") + line
