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


# WEB

web = Host("WEB-01")

dhcp.req_ip(web, web.interfaces[0])
network.add_host(web)

network.add_service(
    web,
    Service( "HTTP", "TCP", 80, "running" )
)


# PC

pc = Host("PC-01")

dhcp.req_ip(pc, pc.interfaces[0])
network.add_host(pc)

# Switch

switch= Switch("SW-01", network.add_event)


# ARP

destination_mac = network.arp.resolve(
    pc,
    web.get_ip()
)


pc_port = switch.connect(pc)
web_port = switch.connect(web)


# IP PACKET

packet = Packet(
    source_ip=pc.get_ip(),
    destination_ip=web.get_ip(),
    protocol="TCP",
    payload="Hello WEB-01!"
)


# ETHERNET FRAME

frame = EthernetFrame(
    source_mac=pc.interfaces[0].mac,
    destination_mac=destination_mac,
    payload=packet
)


# TRANSMIT
""" 
result = network.transmit_frame(
    frame,
    web
) """


#print("TRANSMISSION RESULT")
#print(result)
#
#print("\nFRAME")
#print(frame)

print("\nPORT ASSIGNMENTS")
print("PC-01:", pc_port)
print("WEB-01:", web_port)

print("PORTS")
#print(",\n".join(f"{k}: {v}" for k, v in switch.ports.items()))

for number, port in switch.ports.items():

    print(f"\nPort {number}")

    print("Port object:", port)

    print("Link:", port.link)

    print("Endpoint A:", port.link.endpointA)
    print("Endpoint B:", port.link.endpointB)

unknown_frame = EthernetFrame(
    source_mac=pc.interfaces[0].mac,
    destination_mac="02:FF:FF:FF:FF:FF",
    payload=packet
)

response = EthernetFrame(
    source_mac=web.interfaces[0].mac,
    destination_mac=pc.interfaces[0].mac,
    payload="Hello PC!"
)

pc.interfaces[0].send(frame)
web.interfaces[0].send(response)
pc.interfaces[0].send(frame)

print("\nMAC TABLE")
print(",\n".join(f"{k}: {v}" for k, v in switch.mac_table.items()))

print("\nEVENTS")

for event in network.events:
    print(event)