from backend.core.host import Host
from backend.core.service import Service

from backend.network.network import Network
from backend.network.dhcp import DHCP
from backend.network.packet import Packet
from backend.network.switch import Switch
from backend.network.router import Router
from backend.network.udp import UDPConnection


# ============================================================
# NETWORK
# ============================================================

network = Network("UDP Network")

network.add_subnet(
    "10.0.0.0/24",
    "10.0.0.1"
)

network.add_subnet(
    "10.0.1.0/24",
    "10.0.1.1"
)

network.add_subnet(
    "10.0.2.0/24",
    "10.0.2.1"
)


# ============================================================
# DHCP
# ============================================================

dhcp = DHCP(network)

dhcp.add_scope(
    subnet="10.0.0.0/24",
    start_ip="10.0.0.100",
    end_ip="10.0.0.254",
    gateway="10.0.0.1"
)

dhcp.add_scope(
    subnet="10.0.2.0/24",
    start_ip="10.0.2.100",
    end_ip="10.0.2.254",
    gateway="10.0.2.1"
)


# ============================================================
# WEB SERVER
# ============================================================

web = Host("WEB-01")

web.interfaces[0].attach_network(network)

dhcp.req_ip(
    web.interfaces[0],
    "10.0.0.0/24"
)

network.add_host(web)

network.add_service(
    web,
    Service( "DNS", "UDP", 53, "running"
    )
)

network.start_service(
    web,
    "DNS"
)


# ============================================================
# CLIENT
# ============================================================

pc = Host("PC-01")

pc.interfaces[0].attach_network(network)

dhcp.req_ip(
    pc.interfaces[0],
    "10.0.2.0/24"
)

network.add_host(pc)


# ============================================================
# SWITCHES
# ============================================================

sw1 = Switch("SW-01", network)
sw2 = Switch("SW-02", network)

sw1.connect(web)
sw2.connect(pc)


# ============================================================
# ROUTERS
# ============================================================

router1 = Router("RUT-01", network)
router2 = Router("RUT-02", network)


router1.update_intf(
    router1.eth0,
    ip="10.0.0.1",
    subnet="10.0.0.0/24"
)

router1.update_intf(
    router1.eth1,
    ip="10.0.1.1",
    subnet="10.0.1.0/24"
)

router2.update_intf(
    router2.eth0,
    ip="10.0.1.2",
    subnet="10.0.1.0/24"
)

router2.update_intf(
    router2.eth1,
    ip="10.0.2.1",
    subnet="10.0.2.0/24"
)


# ============================================================
# ROUTER CONNECTIONS
# ============================================================

sw1.connect_router(router1.eth0)
sw2.connect_router(router2.eth1)

from backend.network.link import Link

router1.eth1.connect_link(
    Link(
        router1.eth1,
        router2.eth0
    )
)

router2.eth0.connect_link(
    router1.eth1.link
)


# ============================================================
# ROUTES
# ============================================================

router1.add_route(
    destination="10.0.2.0/24",
    interface=router1.eth1,
    next_hop="10.0.1.2"
)

router2.add_route(
    destination="10.0.0.0/24",
    interface=router2.eth0,
    next_hop="10.0.1.1"
)


# ============================================================
# UDP CONNECTION
# ============================================================

client_udp = UDPConnection(
    local_ip=pc.interfaces[0].ip,
    local_port=49152,
    remote_ip=web.interfaces[0].ip,
    remote_port=53,
    network=network
)

client_key = (
    client_udp.remote_ip,
    client_udp.remote_port,
    client_udp.local_ip,
    client_udp.local_port
)

pc.udp_connections[client_key] = client_udp


# ============================================================
# UDP HELPER
# ============================================================

def udp_to_ip_packet(
    source_interface,
    destination_ip,
    udp_packet
):
    return Packet(
        source_ip=source_interface.ip,
        destination_ip=destination_ip,
        protocol="UDP",
        payload=udp_packet
    )


# ============================================================
# UDP DATAGRAM
# ============================================================

print("\n=== UDP DATAGRAM ===")

datagram = client_udp.send(
    b"DNS QUERY: example.com"
)

print("CLIENT DATAGRAM:", datagram)


udp_ip = udp_to_ip_packet(
    pc.interfaces[0],
    web.interfaces[0].ip,
    datagram
)


# ============================================================
# NETWORK TRANSMISSION
# ============================================================

print("\n=== NETWORK: UDP ===")

result = pc.interfaces[0].send_ip_packet(
    udp_ip
)

print("NETWORK RESULT:", result)


# ============================================================
# UDP CLOSED PORT
# ============================================================

print("\n=== UDP CLOSED PORT ===")

closed_udp = UDPConnection(
    local_ip=pc.interfaces[0].ip,
    local_port=49153,
    remote_ip=web.interfaces[0].ip,
    remote_port=9999,
    network=network
)

closed_datagram = closed_udp.send(
    b"TEST DATAGRAM"
)

closed_udp_ip = udp_to_ip_packet(
    pc.interfaces[0],
    web.interfaces[0].ip,
    closed_datagram
)

result = pc.interfaces[0].send_ip_packet(
    closed_udp_ip
)

print("NETWORK RESULT:", result)


# ============================================================
# ROUTING TABLES
# ============================================================

print("\n=== ROUTING TABLES ===")

print("\nRUT-01")

for route in router1.routes:
    print(
        f"{route['destination']} -> "
        f"{route['interface'].name} -> "
        f"{route['next_hop'] or 'Directly Connected'}"
    )


print("\nRUT-02")

for route in router2.routes:
    print(
        f"{route['destination']} -> "
        f"{route['interface'].name} -> "
        f"{route['next_hop'] or 'Directly Connected'}"
    )


# ============================================================
# SOC TELEMETRY
# ============================================================

print("\n=== SOC TELEMETRY EVENTS ===")

for event in network.events:

    timestamp = event.timestamp.strftime('%H:%M:%S')
    e_type = f"{event.type:<25}"

    endpoints = f"{event.source} -> {event.destination}"
    ep_fmt = f"{endpoints:<42}"

    protocol = f"({event.protocol})".ljust(12)

    print(
        f"  [{timestamp}] "
        f"{e_type} | "
        f"{ep_fmt} "
        f"{protocol} "
        f"{event.metadata}"
    )

