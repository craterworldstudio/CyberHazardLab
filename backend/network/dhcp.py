import ipaddress
import time
from typing import Any

class DHCPScope:
    def __init__(self, subnet: str, start_ip: str, end_ip: str, gateway: str, dns: str = "8.8.8.8", lease_time: int = 120, dhcp=None):
        self.network = ipaddress.ip_network(subnet, strict=False)
        self.start_ip = ipaddress.ip_address(start_ip)
        self.end_ip = ipaddress.ip_address(end_ip)
        self.gateway = gateway
        self.dns = dns
        self.lease_time = lease_time
        self.dhcp = dhcp
        # mac -> {"ip": str, "expires_at": float, "state": "OFFERED" | "COMMITTED"}
        self.leases: dict[str, dict] = {}

    def contains(self, ip: str) -> bool:
        try:
            return ipaddress.ip_address(ip) in self.network
        except Exception:
            return False

    def _cleanup_expired(self):
        now = time.time()
        expired = [mac for mac, lease in self.leases.items() if lease["expires_at"] < now]
        for mac in expired:
            del self.leases[mac]

    def offer(self, mac: str) -> str:
        self._cleanup_expired()
        mac = mac.upper()
        if mac in self.leases:
            self.leases[mac]["expires_at"] = time.time() + 30
            self.leases[mac]["state"] = "OFFERED"
            return self.leases[mac]["ip"]

        used_ips = {lease["ip"] for lease in self.leases.values()}
        used_ips.add(self.gateway)
        if self.dhcp:
            used_ips.update(self.dhcp.get_configured_ips(exclude_mac=mac))

        for val in range(int(self.start_ip), int(self.end_ip) + 1):
            cand = str(ipaddress.ip_address(val))
            if cand not in used_ips:
                self.leases[mac] = {
                    "ip": cand,
                    "expires_at": time.time() + 30,
                    "state": "OFFERED"
                }
                return cand

        raise RuntimeError(f"DHCP Pool Exhausted in {self.network}")

    def validate_lease(self, mac: str, req_ip: str) -> bool:
        """Validates whether a client's requested IP is acceptable (RFC 2131 INIT-REBOOT / Renewal)."""
        self._cleanup_expired()
        mac = mac.upper()
        if not self.contains(req_ip):
            return False

        # If already leased to this MAC, refresh and return True
        if mac in self.leases and self.leases[mac]["ip"] == req_ip:
            self.leases[mac]["expires_at"] = time.time() + self.lease_time
            self.leases[mac]["state"] = "COMMITTED"
            return True

        # Check if leased to someone else or matches static gateway / server
        used_ips = {l["ip"] for m, l in self.leases.items() if m != mac}
        used_ips.add(self.gateway)
        if self.dhcp:
            used_ips.update(self.dhcp.get_configured_ips(exclude_mac=mac))

        if req_ip not in used_ips:
            self.leases[mac] = {
                "ip": req_ip,
                "expires_at": time.time() + self.lease_time,
                "state": "COMMITTED"
            }
            return True

        return False

    def commit(self, mac: str, req_ip: str) -> bool:
        return self.validate_lease(mac, req_ip)

    def release(self, mac: str) -> bool:
        mac = mac.upper()
        if mac in self.leases:
            del self.leases[mac]
            return True
        return False


class DHCP:
    """Manages DHCP scopes for the network simulation."""
    def __init__(self, network=None, start_ip=None, end_ip=None):
        self.network = network
        self.scopes: list[DHCPScope] = []
        if start_ip and end_ip:
            self.add_scope("10.0.0.0/24", start_ip, end_ip, "10.0.0.1")

    def req_ip(self, a, b=None):
        interface = None
        subnet = None

        if hasattr(a, "interfaces") and b is not None:
            # req_ip(host, interface)
            interface = b
            subnet = str(self.scopes[0].network) if self.scopes else "10.0.0.0/24"
        elif hasattr(a, "mac") and (isinstance(b, str) or b is None):
            # req_ip(interface, subnet)
            interface = a
            subnet = str(b) if b else (str(self.scopes[0].network) if self.scopes else "10.0.0.0/24")
        elif hasattr(b, "mac"):
            interface = b
            subnet = str(a)
        else:
            interface = a
            subnet = "10.0.0.0/24"

        scope = self.get_scope(str(subnet))
        if not scope:
            scope = self.auto_provision_scope(str(subnet))
        if not scope:
            raise ValueError(f"No DHCP scope exists for {subnet}")

        ip = scope.offer(interface.mac)
        scope.commit(interface.mac, ip)
        interface.ip = ip
        interface.subnet = str(scope.network)
        if interface.owner and hasattr(interface.owner, "_install_connected_route"):
            interface.owner._install_connected_route(interface)
        return ip

    def get_configured_ips(self, exclude_mac: str | None = None) -> set[str]:
        ips = set()
        if not self.network:
            return ips
        devices = []
        if hasattr(self.network, "hosts"):
            devices.extend(self.network.hosts.values())
        if hasattr(self.network, "routers"):
            devices.extend(self.network.routers.values())
        orch = getattr(self.network, "orchestrator", None)
        if orch:
            if hasattr(orch, "hosts"):
                devices.extend(orch.hosts.values())
            if hasattr(orch, "routers"):
                devices.extend(orch.routers.values())
        for dev in set(devices):
            for intf in getattr(dev, "interfaces", []):
                if intf.ip and intf.ip not in ("0.0.0.0", ""):
                    if exclude_mac and intf.mac.upper() == exclude_mac.upper():
                        continue
                    ips.add(intf.ip)
        return ips

    def add_scope(self, subnet: str, start_ip: str, end_ip: str, gateway: str, dns: str = "8.8.8.8", lease_time: int = 120) -> DHCPScope:
        # Avoid duplicate scope for same network
        net = ipaddress.ip_network(subnet, strict=False)
        for s in self.scopes:
            if s.network == net:
                s.start_ip = ipaddress.ip_address(start_ip)
                s.end_ip = ipaddress.ip_address(end_ip)
                s.gateway = gateway
                s.dns = dns
                s.lease_time = lease_time
                s.dhcp = self
                return s

        scope = DHCPScope(subnet, start_ip, end_ip, gateway, dns, lease_time, dhcp=self)
        self.scopes.append(scope)
        return scope

    def get_scope(self, subnet_or_ip: str) -> DHCPScope | None:
        try:
            # Check direct subnet match
            target_net = ipaddress.ip_network(subnet_or_ip, strict=False)
            for s in self.scopes:
                if s.network == target_net:
                    return s
        except Exception:
            pass

        # Check contains IP
        try:
            target_ip = ipaddress.ip_address(subnet_or_ip)
            for s in self.scopes:
                if target_ip in s.network:
                    return s
        except Exception:
            pass

        return None

    def auto_provision_scope(self, subnet_or_ip: str, default_gateway: str | None = None) -> DHCPScope | None:
        """Dynamically create a scope if none exists."""
        scope = self.get_scope(subnet_or_ip)
        if scope:
            return scope

        try:
            # If it's an IP (e.g. 10.0.0.5), infer /24
            if "/" not in subnet_or_ip:
                ip_obj = ipaddress.ip_address(subnet_or_ip)
                net = ipaddress.ip_network(f"{subnet_or_ip}/24", strict=False)
            else:
                net = ipaddress.ip_network(subnet_or_ip, strict=False)

            hosts = list(net.hosts())
            if len(hosts) < 4:
                return None

            gateway = default_gateway or str(hosts[0])
            start_ip = str(hosts[10]) if len(hosts) > 11 else str(hosts[1])
            end_ip = str(hosts[-2])

            return self.add_scope(str(net), start_ip, end_ip, gateway)
        except Exception:
            return None
