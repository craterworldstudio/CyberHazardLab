from backend import Simulation
import pprint

from backend.network.packet import ICMPPacket, Packet

# ============================================================
# SIMULATION
# ============================================================

sim = Simulation("Orchestrator Test")


# ============================================================
# SUBNETS
# ============================================================

sim.add_subnet(
    "10.0.0.0/24",
    "10.0.0.1"
)

sim.add_subnet(
    "10.0.1.0/24",
    "10.0.1.1"
)

sim.add_subnet(
    "10.0.2.0/24",
    "10.0.2.1"
)


# ============================================================
# DHCP
# ============================================================

sim.add_dhcp_scope(
    subnet="10.0.0.0/24",
    start_ip="10.0.0.100",
    end_ip="10.0.0.254",
    gateway="10.0.0.1"
)

sim.add_dhcp_scope(
    subnet="10.0.2.0/24",
    start_ip="10.0.2.100",
    end_ip="10.0.2.254",
    gateway="10.0.2.1"
)


# ============================================================
# HOSTS
# ============================================================

web = sim.add_host(
    "WEB-01",
    "10.0.0.0/24",
    sim.get_device_type("server")
)

pc = sim.add_host(
    "PC-01",
    "10.0.2.0/24"
)


# ============================================================
# SERVICES
# ============================================================

sim.add_service(
    web,
    "DNS",
    "UDP",
    53
)

sim.start_service(
    web,
    "DNS"
)


# ============================================================
# SWITCHES
# ============================================================

sw1 = sim.add_switch("SW-01")
sw2 = sim.add_switch("SW-02")

sim.connect_host_to_switch(
    web,
    sw1
)

sim.connect_host_to_switch(
    pc,
    sw2
)


# ============================================================
# ROUTERS
# ============================================================

router1 = sim.add_router("RUT-01")
router2 = sim.add_router("RUT-02")


# ------------------------------------------------------------
# RUT-01
# ------------------------------------------------------------

sim.configure_router_interface(
    router1,
    router1.eth0,
    ip="10.0.0.1",
    subnet="10.0.0.0/24"
)

sim.configure_router_interface(
    router1,
    router1.eth1,
    ip="10.0.1.1",
    subnet="10.0.1.0/24"
)


# ------------------------------------------------------------
# RUT-02
# ------------------------------------------------------------

sim.configure_router_interface(
    router2,
    router2.eth0,
    ip="10.0.1.2",
    subnet="10.0.1.0/24"
)

sim.configure_router_interface(
    router2,
    router2.eth1,
    ip="10.0.2.1",
    subnet="10.0.2.0/24"
)


# ============================================================
# ROUTER CONNECTIONS
# ============================================================

sim.connect_router_interface(
    sw1,
    router1.eth0
)

sim.connect_router_interface(
    sw2,
    router2.eth1
)

sim.connect_router_interfaces(
    router1.eth1,
    router2.eth0
)


# ============================================================
# ROUTES
# ============================================================

sim.add_route(
    router1,
    destination="10.0.2.0/24",
    interface=router1.eth1,
    next_hop="10.0.1.2"
)

sim.add_route(
    router2,
    destination="10.0.0.0/24",
    interface=router2.eth0,
    next_hop="10.0.1.1"
)


# ============================================================
# UDP CONNECTION
# ============================================================

print("\n=== UDP TEST ===")

udp = sim.create_udp_connection(
    source=pc,
    source_port=49152,
    destination=web,
    destination_port=53
)

print(
    "UDP:",
    udp.local_ip,
    udp.local_port,
    "->",
    udp.remote_ip,
    udp.remote_port
)


# ============================================================
# UDP DATAGRAM
# ============================================================

result = sim.udp_send(
    udp,
    b"DNS QUERY: example.com"
)

print("\nNETWORK RESULT:")
print(result)

#sim.stop_service(web,"DNS")

# ============================================================
# TCP SERVICE
# ============================================================

print("\n=== TCP TEST ===")



sim.add_service(
    web,
    "HTTP",
    "TCP",
    80
)

sim.start_service(
    web,
    "HTTP"
)


# ============================================================
# TCP CONNECTION
# ============================================================

tcp = sim.create_tcp_connection(
    source=pc,
    source_port=49153,
    destination=web,
    destination_port=80
)

print(
    "TCP:",
    tcp.local_ip,
    tcp.local_port,
    "->",
    tcp.remote_ip,
    tcp.remote_port
)


# ============================================================
# TCP CONNECT
# ============================================================

result = sim.tcp_connect(tcp)

print("\nNETWORK RESULT:")
print(result)

print(
    "\nCLIENT TCP STATE:",
    tcp.state
)

result = sim.ping(
    source="PC-01",
    destination_ip="10.0.0.100",
    ttl=32
)

print("\nPING RESULT:")
print(result)

result = sim.traceroute(
    source="PC-01",
    destination_ip="10.0.0.100"
)

print("\nTRACEROUTE RESULT:")

for hop in result:
    print(hop)

# ============================================================
# STATE
# ============================================================

print("\n=== SIMULATION STATE ===")

state = sim.get_state()

pprint.pprint(state, indent=4, width=40)


# ============================================================
# TELEMETRY
# ============================================================

print("\n=== SOC TELEMETRY EVENTS ===")

for event in sim.get_events():

    timestamp = event.timestamp.strftime("%H:%M:%S")

    e_type = f"{event.type:<30}"

    endpoints = (
        f"{event.source} -> {event.destination}"
    )

    ep_fmt = f"{endpoints:<45}"

    protocol = (
        f"({event.protocol})".ljust(12)
    )

    print(
        f"  [{timestamp}] "
        f"{e_type} | "
        f"{ep_fmt} "
        f"{protocol} "
        f"{event.metadata}"
    )

