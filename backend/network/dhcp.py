from ..core.host import Host
from ..core.event import Event
from ..core.interface import NetworkInterface
from ipaddress import ip_address, ip_network

class DHCPScope:

    def __init__(self, subnet, start_ip, end_ip, gateway):
        self.network = ip_network(subnet)
        self.start_ip = ip_address(start_ip)
        self.end_ip = ip_address(end_ip)
        self.gateway = gateway
        self.leases = {}

    def contains(self, ip):
        return ip_address(ip) in self.network

    def allocate(self, intf):
        
        for lease_intf_mac in self.leases.keys():
            if intf.mac == lease_intf_mac:

                return self.leases[intf]

        for value in range(
            int(self.start_ip),
            int(self.end_ip) + 1
        ):
            ip = str(ip_address(value))

            if ip not in self.leases.values():
                self.leases[intf.mac] = ip
                return ip

        raise RuntimeError(
            f"DHCP Pool Exhausted in {self.network}"
        )

    

class DHCP:

    def __init__(self, network):
        self.network = network
        self.scopes = []

        """         
        self.start = ip_address(start_ip)
        self.end = ip_address(end_ip)

        if self.start not in network.subnet:
            raise ValueError("DHCP start IP is outside the network")

        if self.end not in network.subnet:
            raise ValueError("DHCP end IP is outside the network")

        self.leases = {}
        """
    def add_scope(self, subnet, start_ip, end_ip, gateway):
        scope = DHCPScope(
            subnet=subnet,
            start_ip=start_ip,
            end_ip=end_ip,
            gateway=gateway
        )

        self.scopes.append(scope)

        return scope

    def get_scope(self, subnet):
        network = ip_network(subnet)
    
        for scope in self.scopes:
            if scope.network == network:
                return scope
    
        return None

    def req_ip(self, interface: NetworkInterface, subnet):

        scope = self.get_scope(subnet)

        if scope is None:
            raise ValueError(
                f"No DHCP scope exists for {subnet}"
            )
        ip = scope.allocate(interface)

        interface.ip = ip
        interface.subnet = str(scope.network)

        self.network.add_event(
            Event(
                type="DHCP_LEASE",
                source="DHCP",
                protocol="DHCP",
                destination=ip,
                metadata={
                    "ip": ip,
                    "intf_name": interface.name,
                    "gateway": scope.gateway
                }
            )
        )

        return ip


    '''def req_ip(self, host: Host, interface: NetworkInterface, subnet=ip_address("10.0.0.0/24")):
        if host.name in self.leases:
            return self.leases[host.name]

        current = self.start

        while current <= self.end:
            ip = str(current)

            if ip not in self.leases.values():
                self.leases[host.name] = ip

                interface.ip = ip


                self.network.add_event(
                    Event(
                        type="DHCP_LEASE",
                        source="DHCP",
                        protocol="DHCP",

                        destination=host.name,
                        metadata={
                            "ip": ip,
                            "intf_name": interface.name,
                            "gateway": self.network.gateway
                        }
                    )
                )


                return ip

            current += 1

        raise RuntimeError("DHCP Pool Exhausted")'''