from backend.core.host import Host
from backend.core.service import Service

from backend.network.network import Network
from backend.network.dhcp import DHCP
from backend.network.packet import Packet
from backend.network.frame import EthernetFrame

from backend.network.switch import Switch
from backend.network.router import Router

network = Network( name="Home Lab" )

dhcp = DHCP(
    network
)

network.add_subnet("10.0.0.0/24", "10.0.0.1")
network.add_subnet("10.0.1.0/24", "10.0.1.1")

dhcp.add_scope(
    subnet="10.0.0.0/24",
    start_ip="10.0.0.100",
    end_ip="10.0.0.255",
    gateway="10.0.0.1"                 #Router's eth0 as gateway
)

dhcp.add_scope(
    subnet="10.0.1.0/24",
    start_ip="10.0.1.100",
    end_ip="10.0.1.255",
    gateway="10.0.1.1"                 #Router's eth1 as gateway
)



web = Host("WEB-01")
web.interfaces[0].attach_network(network)
dhcp.req_ip(web.interfaces[0], "10.0.0.0/24")
network.add_host(web)

network.add_service(
    web,
    Service( "HTTP", "TCP", 80, "running" )
)




pc = Host("PC-01")
pc.interfaces[0].attach_network(network)
dhcp.req_ip(pc.interfaces[0], "10.0.1.0/24")
network.add_host(pc)



switch1 = Switch("SW-01", network)
switch2 = Switch("SW-02", network)

web_port = switch1.connect(web)
pc_port = switch2.connect(pc)


#trunk1, trunk2 = switch1.connect_switch(switch2)

router = Router("RUT-01", network)
router.update_intf(router.eth0, subnet="10.0.0.0/24")
router.update_intf(router.eth1, subnet="10.0.1.0/24")

swt1rut = switch1.connect_router(router.eth0)
swt2rut = switch2.connect_router(router.eth1)




print("\n=== SUBNETS ===")

for subnet, config in network.subnets.items():
    print(
        f"{subnet} -> gateway={config['gateway']}"
    )


print("\n=== DHCP SCOPES ===")

for scope in dhcp.scopes:
    print(
        f"{scope.network} -> "
        f"{scope.start_ip} - {scope.end_ip}, "
        f"gateway={scope.gateway}"
    )


print("\n=== HOSTS ===")

for host in network.hosts.values():

    print(f"\n{host.name}")

    for interface in host.interfaces:
        print(
            f"  {interface.name}: "
            f"IP={interface.ip}, "
            f"MAC={interface.mac}"
        )


print("\n=== SWITCHES ===")

for switch in [switch1, switch2]:

    print(f"\n{switch.name}")

    for number, port in switch.ports.items():
        print(
            f"  Port {number}: "
            f"mode={port.mode}, "
            f"link={port.link}"
        )


print("\n=== ROUTER ===")

print(router.name)

for interface in router.interfaces:
    print(
        f"  {interface.name}: "
        f"IP={interface.ip}, "
        f"MAC={interface.mac}"
    )

print("\n \t === ROUTER LINKS ===")

print("\t SW-01 -> Router:")
print("\t Switch port:", swt1rut)
print("\t Link:", swt1rut.link)
print("\t A:", swt1rut.link.endpointA)
print("\t B:", swt1rut.link.endpointB)

print("\n \tSW-02 -> Router:")
print("\t Switch port:", swt2rut)
print("\t Link:", swt2rut.link)
print("\t A:", swt2rut.link.endpointA)
print("\t B:", swt2rut.link.endpointB)

print("\n\t=== ROUTER CONNECTIONS ===")

print("\teth0:", router.eth0.link)
print("\teth1:", router.eth1.link)

print("\tSW-01 port:", swt1rut.port_number)
print("\tSW-01 mode:", swt1rut.mode)

print("\tSW-02 port:", swt2rut.port_number)
print("\tSW-02 mode:", swt2rut.mode)


packet = Packet(
    source_ip=pc.interfaces[0].ip,
    destination_ip=web.interfaces[0].ip,
    protocol="TCP",
    payload="Hello WEB from another subnet!"
)

print("\n=== SENDING ===")

result = pc.interfaces[0].send_ip_packet(packet)

print("\nRESULT:")
print(result)


print("\n=== MAC TABLES - ROUTE TABLES===")

print("\nSW-01")

for mac, port in switch1.mac_table.items():
    print(f"{mac} -> Port {port}")

print("\nSW-02")

for mac, port in switch2.mac_table.items():
    print(f"{mac} -> Port {port}")

print("\n RUT-01")

for route in router.routes:
    print(route)

print("\n=== EVENTS ===")

for event in network.events:
    print(event)