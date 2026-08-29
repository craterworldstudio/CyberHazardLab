from backend.core.host import Host
from backend.core.service import Service

from backend.network.network import Network
from backend.network.dhcp import DHCP
from backend.network.packet import Packet
from backend.network.frame import EthernetFrame

from backend.network.switch import Switch

network = Network(
    name="Home Lab",
    subnet="10.0.0.0/24",
    gateway="10.0.0.1"
)

dhcp = DHCP(
    network,
    "10.0.0.100",
    "10.0.0.200"
)




web = Host("WEB-01")
web.interfaces[0].attach_network(network)
dhcp.req_ip(web, web.interfaces[0])
network.add_host(web)

network.add_service(
    web,
    Service( "HTTP", "TCP", 80, "running" )
)




pc = Host("PC-01")
pc.interfaces[0].attach_network(network)
dhcp.req_ip(pc, pc.interfaces[0])
network.add_host(pc)



switch= Switch("SW-01", network)

pc_port = switch.connect(pc)
web_port = switch.connect(web)





print("ARP CACHE")
print(network.arp.cache)



packet = Packet(
    source_ip=pc.interfaces[0].ip,
    destination_ip=web.interfaces[0].ip,
    protocol="TCP",
    payload="Hello WEB!"
)




result = pc.interfaces[0].send_ip_packet(packet)

print("RESULT:", result)


print("ARP CACHE:", network.arp.cache)


print("\n--- SECOND PACKET ---")

result = pc.interfaces[0].send_ip_packet(packet)

print("RESULT:", result)
print("ARP CACHE:", network.arp.cache)


print("\nMAC TABLE")
print(",\n".join(f"{k}: {v}" for k, v in switch.mac_table.items()))


print("\nEVENTS")

for event in network.events:
    print(event)