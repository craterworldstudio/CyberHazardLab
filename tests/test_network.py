from backend.network.network import Network
from backend.core.host import Host
from backend.core.service import Service
from backend.core.event import Event
from backend.network.dhcp import DHCP
from backend.network.arp import ARP
from backend.network import packet, frame


network = Network(name="Home Lab",
    subnet="10.0.0.0/24",
    gateway="10.0.0.1"
)
arp = ARP(network=network)

dhcp = DHCP(network, "10.0.0.100", "10.0.0.255")

web = Host("WEB-01")
dhcp.req_ip(web, web.interfaces[0])
network.add_host(web)

network.add_service(web, Service("HTTP", "TCP", 80))
network.start_service(web, "HTTP")



pc = Host("PC-01")
dhcp.req_ip(pc, pc.interfaces[0])

network.add_host(pc)

network.connect(pc, web, "TCP", 80)
#network.connect(pc, web, "TCP", 80)

print("NETWORK")
print("Name: ", network.name)
print("Subnet: ", network.subnet)
print("Gateway:", network.gateway)

print("\nHOSTS")

for host in network.hosts.values():
    print(host)

print("\nDHCP LEASES")
print(dhcp.leases)

print("\nEVENTS")

for event in network.events:
    print(event)