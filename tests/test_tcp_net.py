from backend.core.host import Host
from backend.core.service import Service

from backend.network.network import Network
from backend.network.dhcp import DHCP
from backend.network.packet import Packet
from backend.network.switch import Switch
from backend.network.router import Router
from backend.network.tcp import TCPConnection


# ============================================================
# NETWORK
# ============================================================

network = Network("TCP Network")

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
    web, Service(
        "HTTP", "TCP", 80, "running"
    )
)
network.start_service(
    web,
    "HTTP"
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


router1.update_intf( router1.eth0, ip="10.0.0.1", subnet="10.0.0.0/24" )
router1.update_intf( router1.eth1, ip="10.0.1.1", subnet="10.0.1.0/24" )
router2.update_intf( router2.eth0, ip="10.0.1.2", subnet="10.0.1.0/24" )
router2.update_intf( router2.eth1, ip="10.0.2.1", subnet="10.0.2.0/24" )


# ============================================================
# ROUTER CONNECTIONS
# ============================================================

sw1.connect_router(router1.eth0)
sw2.connect_router(router2.eth1)

# Router-to-router transit network
from backend.network.link import Link

router1.eth1.connect_link( Link(router1.eth1, router2.eth0) )

router2.eth0.connect_link( router1.eth1.link )


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
# TCP CONNECTION OBJECT
# ============================================================

client_tcp = TCPConnection(
    local_ip=pc.interfaces[0].ip,
    local_port=49152,
    remote_ip=web.interfaces[0].ip,
    remote_port=80,
    network=network
)

client_key = (
    client_tcp.remote_ip,
    client_tcp.remote_port,
    client_tcp.local_ip,
    client_tcp.local_port
)

pc.tcp_connections[client_key] = client_tcp


# ============================================================
# TCP HELPER
# ============================================================

def tcp_to_ip_packet(
    source_interface,
    destination_ip,
    tcp_packet
):
    return Packet(
        source_ip=source_interface.ip,
        destination_ip=destination_ip,
        protocol="TCP",
        payload=tcp_packet
    )


# ============================================================
# TCP SYN
# ============================================================

print("\n=== TCP CONNECTION ===")

syn = client_tcp.connect()

print("CLIENT STATE:", client_tcp.state)
print("SYN:", syn)

syn_ip = tcp_to_ip_packet(
    pc.interfaces[0],
    web.interfaces[0].ip,
    syn
)

print("\n=== NETWORK: SYN ===")

result = pc.interfaces[0].send_ip_packet(
    syn_ip
)

print("NETWORK RESULT:", result)

print("\nCLIENT STATE:", client_tcp.state)

# ============================================================
# TCP TERMINATION
# ============================================================

print("\n=== TCP TERMINATION ===")

# Get the server-side connection created by WEB-01
server_key = (
    pc.interfaces[0].ip,
    49152,
    web.interfaces[0].ip,
    80
)

server_tcp = web.tcp_connections[server_key]

print("CLIENT STATE:", client_tcp.state)
print("SERVER STATE:", server_tcp.state)


# ------------------------------------------------------------
# CLIENT -> SERVER : FIN
# ------------------------------------------------------------

fin = client_tcp.close()

print("\nCLIENT -> SERVER:", fin)
print("CLIENT STATE:", client_tcp.state)

fin_ip = tcp_to_ip_packet(
    pc.interfaces[0],
    web.interfaces[0].ip,
    fin
)

print("\n=== NETWORK: FIN ===")

result = pc.interfaces[0].send_ip_packet(fin_ip)

print("NETWORK RESULT:", result)


# ------------------------------------------------------------
# SERVER -> CLIENT : FIN-ACK
# ------------------------------------------------------------

print("\nCLIENT STATE:", client_tcp.state)
print("SERVER STATE:", server_tcp.state)

server_key = (
    pc.interfaces[0].ip,
    49152,
    web.interfaces[0].ip,
    80
)

server_tcp = web.tcp_connections[server_key]

print("\n=== SERVER CLOSE ===")

print("CLIENT STATE:", client_tcp.state)
print("SERVER STATE:", server_tcp.state)

server_fin = server_tcp.close()

print("\nSERVER -> CLIENT:", server_fin)
print("SERVER STATE:", server_tcp.state)

server_fin_ip = tcp_to_ip_packet(
    web.interfaces[0],
    pc.interfaces[0].ip,
    server_fin
)

print("\n=== NETWORK: SERVER FIN ===")

result = web.interfaces[0].send_ip_packet(
    server_fin_ip
)

print("NETWORK RESULT:", result)

print("\nCLIENT STATE:", client_tcp.state)
print("SERVER STATE:", server_tcp.state)


print("\n=== TIME WAIT ===")

print("CLIENT STATE:", client_tcp.state)
print("SERVER STATE:", server_tcp.state)

client_tcp.tick(59)

print("AFTER 59s:")
print("CLIENT STATE:", client_tcp.state)

client_tcp.tick(1)

print("AFTER 60s:")
print("CLIENT STATE:", client_tcp.state)


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


print("\n=== SOC TELEMETRY EVENTS ===")
for event in network.events:
    timestamp = event.timestamp.strftime('%H:%M:%S')
    e_type    = f"{event.type:<20}"
    endpoints = f"{event.source} -> {event.destination}"
    ep_fmt    = f"{endpoints:<42}"
    protocol  = f"({event.protocol})".ljust(12)
    
    print(f"  [{timestamp}] {e_type} | {ep_fmt} {protocol} {event.metadata}")