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
        
        # Default interface eth0
        self.add_interface(NetworkInterface(
            name="eth0",
            mac=generate_mac(),
            ip="0.0.0.0",
            subnet="0.0.0.0/0",
            owner=self
        ))
        
        self._generate_system_files()
        
    def _generate_system_files(self):
        vfs = self.vfs
        from backend.database.fs import Folder, File
        
        # Ensure /etc exists
        vfs.curr_fol = vfs.tree
        etc = vfs.get_item("etc")
        if not etc:
            etc = Folder("etc")
            etc.parent = vfs.tree
            etc.path = "/etc"
            vfs.tree.add(etc)
            
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
            interfaces_file.contents = f"auto {iface.name}\niface {iface.name} inet static\n  address {iface.ip}\n  netmask {iface.subnet.split('/')[1] if '/' in iface.subnet else '0'}\n  mac {iface.mac}"

        # Ensure /mnt exists
        vfs.curr_fol = vfs.tree
        mnt = vfs.get_item("mnt")
        if not mnt:
            mnt = Folder("mnt")
            mnt.parent = vfs.tree
            mnt.path = "/mnt"
            vfs.tree.add(mnt)
            
        # Ensure /home and users exist
        home = vfs.get_item("home")
        if not home:
            home = Folder("home")
            home.parent = vfs.tree
            home.path = "/home"
            vfs.tree.add(home)
            
        for username in self.users.keys():
            if username == "root":
                root_fol = vfs.get_item("root")
                if not root_fol:
                    root_fol = Folder("root")
                    root_fol.owner = "root"
                    root_fol.group = "root"
                    root_fol.perms = "rwx------"
                    root_fol.parent = vfs.tree
                    root_fol.path = "/root"
                    vfs.tree.add(root_fol)
                continue
                
            vfs.curr_fol = home
            user_fol = vfs.get_item(username)
            if not user_fol:
                user_fol = Folder(username)
                user_fol.owner = username
                user_fol.group = username
                user_fol.parent = home
                user_fol.path = f"/home/{username}"
                home.add(user_fol)
                
        # If NAS, auto-mount storage drives
        from backend.core.device import DeviceType
        if self.device_type == DeviceType.NAS:
            from backend.database.fs import Drive
            vfs.curr_fol = mnt
            if not vfs.get_item("D"):
                d_drive = Drive("D")
                d_drive.owner = "root"
                d_drive.group = "root"
                d_drive.parent = mnt
                d_drive.path = "/mnt/D"
                mnt.add(d_drive)
            if not vfs.get_item("E"):
                e_drive = Drive("E")
                e_drive.owner = "root"
                e_drive.group = "root"
                e_drive.parent = mnt
                e_drive.path = "/mnt/E"
                mnt.add(e_drive)
        
        vfs.curr_fol = vfs.tree
