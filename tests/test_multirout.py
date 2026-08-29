import ipaddress
from backend.core.host import Host
from backend.core.service import Service
from backend.network.link import Link
from backend.network.network import Network
from backend.network.dhcp import DHCP
from backend.network.packet import Packet
from backend.network.switch import Switch
from backend.network.router import Router

# Initialize Core Network & Services
network = Network(name="Home Lab")
dhcp = DHCP(network)

# Register Subnets
# Subnet 1: WEB-01 side
network.add_subnet("10.0.0.0/24", "10.0.0.1")
# Subnet 2: Inter-router transit network
network.add_subnet("10.0.1.0/24", "10.0.1.1")
# Subnet 3: PC-01 side (Gateway is now RUT-02: 10.0.2.1)
network.add_subnet("10.0.2.0/24", "10.0.2.1")

# Add DHCP Scopes
dhcp.add_scope(
    subnet="10.0.0.0/24",
    start_ip="10.0.0.100",
    end_ip="10.0.0.255",
    gateway="10.0.0.1"  # RUT01 eth0 gateway
)

dhcp.add_scope(
    subnet="10.0.2.0/24",
    start_ip="10.0.2.100",
    end_ip="10.0.2.255",
    gateway="10.0.2.1"  # RUT02 eth1 gateway
)

# Instantiate Hosts
web = Host("WEB-01")
web.interfaces[0].attach_network(network)
dhcp.req_ip(web.interfaces[0], "10.0.0.0/24")
network.add_host(web)
network.add_service(web, Service("HTTP", "TCP", 80, "running"))

pc = Host("PC-01")
pc.interfaces[0].attach_network(network)
dhcp.req_ip(pc.interfaces[0], "10.0.2.0/24")
network.add_host(pc)

# Instantiate Switches
switch1 = Switch("SW-01", network)
switch2 = Switch("SW-02", network)

web_port = switch1.connect(web)
pc_port = switch2.connect(pc)

# Instantiate Router & Connect Interfaces
router1 = Router("RUT-01", network)
router2 = Router("RUT-02", network)
# Note: Router initialization already configures eth0/eth1 default routes[cite: 1]
# update_intf modifies subnets without creating duplicate routes if updated in router.py[cite: 1]
router1.update_intf(router1.eth0, ip="10.0.0.1", subnet="10.0.0.0/24")
router1.update_intf(router1.eth1, ip="10.0.1.1", subnet="10.0.1.0/24") 

router2.update_intf(router2.eth0, ip="10.0.1.2", subnet="10.0.1.0/24")
router2.update_intf(router2.eth1, ip="10.0.2.1", subnet="10.0.2.0/24")

swt1rut = switch1.connect_router(router1.eth0)
swt2rut = switch2.connect_router(router2.eth1)

router_link = Link(router1.eth1, router2.eth0)
router1.eth1.connect_link(router_link)
router2.eth0.connect_link(router_link)

# RUT-01 needs a route to reach Subnet 3 (10.0.2.0/24) via RUT-02's eth0 IP (10.0.1.2)
router1.add_route(
    destination="10.0.2.0/24", #Subnet 3
    interface=router1.eth1,
    next_hop="10.0.1.2" # Intermediate - Gateway 10.0.1.1 RUT01 eth1 -> 10.0.1.2 RUT02 eth0
)

# RUT-02 needs a route to reach Subnet 1 (10.0.0.0/24) via RUT-01's eth1 IP (10.0.1.1)
router2.add_route(
    destination="10.0.0.0/24", #Subnet 1
    interface=router2.eth0,
    next_hop="10.0.1.1" # Rut02 eth0 10.0.1.2 -> Gateway  Rut01 eth1 10.0.1.1 on subnet 2 => Rut01 eth0 10.0.0.1 Gateway
)

# Display Initial Setup Information
print("\n=== SUBNETS ===")
for subnet, config in network.subnets.items():
    print(f"{subnet} -> gateway={config['gateway']}")

print("\n=== DHCP SCOPES ===")
for scope in dhcp.scopes:
    print(f"{scope.network} -> {scope.start_ip} - {scope.end_ip}, gateway={scope.gateway}")

print("\n=== HOSTS ===")
for host in network.hosts.values():
    print(f"\n{host.name}")
    for interface in host.interfaces:
        print(f"  {interface.name}: IP={interface.ip}, MAC={interface.mac}")

print("\n=== SWITCHES ===")
for switch in [switch1, switch2]:
    print(f"\n{switch.name}")
    for number, port in switch.ports.items():
        print(f"  Port {number}: mode={port.mode}, link={port.link}")

print("\n=== ROUTER ===")
print(router1.name)
for interface in router1.interfaces:
    print(f"  {interface.name}: IP={interface.ip}, MAC={interface.mac}")

print(router2.name)
for interface in router2.interfaces:
    print(f"  {interface.name}: IP={interface.ip}, MAC={interface.mac}")

# Trigger Packet Transmission
packet = Packet(
    source_ip=pc.interfaces[0].ip,
    destination_ip=web.interfaces[0].ip,
    protocol="TCP",
    payload="Hello WEB from another subnet!"
)

print("\n=== SENDING PACKET ===")
result = pc.interfaces[0].send_ip_packet(packet)

print("\nTRANSMISSION RESULT:")
print(result)

# Display Post-Transmission Tables
print("\n=== MAC TABLES ===")
print("SW-01:")
for mac, port in switch1.mac_table.items():
    print(f"  {mac} -> Port {port}")

print("SW-02:")
for mac, port in switch2.mac_table.items():
    print(f"  {mac} -> Port {port}")

print("\n=== ROUTING TABLES ===")
for r_obj in [router1, router2]:
    print(f"\n{r_obj.name}:")
    for route in r_obj.routes:
        dest = route["destination"]
        intf = route["interface"].name
        next_h = route["next_hop"] if route["next_hop"] else "Directly Connected"
        print(f"  Subnet: {dest} | Interface: {intf} | Next Hop: {next_h}")

print("\n=== SOC TELEMETRY EVENTS ===")
for event in network.events:
    #print(f"  [{event.timestamp.strftime('%H:%M:%S')}] {event.type} \t| {event.source} -> {event.destination} \t ({event.protocol}) \t{event.metadata}")

    timestamp = event.timestamp.strftime('%H:%M:%S')
    e_type = f"{event.type:<30}"
    endpoints = f"{event.source} -> {event.destination}"
    ep_formatted = f"{endpoints:<50}"
    protocol = f"({event.protocol})".ljust(12)
    
    print(f"  [{timestamp}] {e_type} | {ep_formatted} {protocol} {event.metadata}")