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



switch1 = Switch("SW-01", network)
switch2 = Switch("SW-02", network)

pc_port = switch1.connect(pc)
web_port = switch2.connect(web)


trunk1, trunk2 = switch1.connect_switch(switch2)


packet = Packet(
    source_ip=pc.interfaces[0].ip,
    destination_ip=web.interfaces[0].ip,
    protocol="TCP",
    payload="Hello diff swt WEB!"
)

request = EthernetFrame(
    source_mac=pc.interfaces[0].mac,
    destination_mac=web.interfaces[0].mac,
    payload="Hello diff swt WEB!"
)

response = EthernetFrame(
    source_mac=web.interfaces[0].mac,
    destination_mac=pc.interfaces[0].mac,
    payload="Hello back!"
)


print("SWT1 PORTS")

for number, port in switch1.ports.items():
    print(number, port.mode, port.link)

print("\nSWT2 PORTS")

for number, port in switch2.ports.items():
    print(number, port.mode, port.link)



#res1 = pc.interfaces[0].send_ip_packet(packet)
res1 = pc.interfaces[0].send(request)
res2 = web.interfaces[0].send(response)


print("\nMAC TABLE\nSwitch1")
print(",\n".join(f"{k}: {v}" for k, v in switch1.mac_table.items()))
print("\nSwitch2")
print(",\n".join(f"{k}: {v}" for k, v in switch2.mac_table.items()))


print("\nEVENTS")

for event in network.events:
    print(event)

#print(res1,"\n",res2)