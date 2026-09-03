from backend import Simulation
from Application.ncm.ncm import NetworkConfigurationManager


# ============================================================
# SIMULATION
# ============================================================

sim = Simulation("NCM Test")
ncm = NetworkConfigurationManager(sim)


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
    subnet="10.0.1.0/24",
    start_ip="10.0.1.100",
    end_ip="10.0.1.254",
    gateway="10.0.1.1"
)


# ============================================================
# HOSTS
# ============================================================

pc1 = sim.add_host(
    "PC-01",
    "10.0.0.0/24"
)

pc2 = sim.add_host(
    "PC-02",
    "10.0.1.0/24"
)


# ============================================================
# SWITCH
# ============================================================

sw1 = sim.add_switch("SW-01")


# ============================================================
# ROUTER
# ============================================================

router1 = sim.add_router("RUT-01")


# ============================================================
# DEVICE TESTS
# ============================================================

print("\n=== NCM DEVICE TESTS ===")


print("\n--- GET DEVICES ---")

for name, device in ncm.get_devices().items():

    print(
        name,
        type(device).__name__
    )


print("\n--- GET DEVICE ---")

print(
    ncm.get_device("PC-01")
)

print(
    ncm.get_device("SW-01")
)

print(
    ncm.get_device("RUT-01")
)


# ============================================================
# INTERFACE TESTS
# ============================================================

print("\n=== NCM INTERFACE TESTS ===")


# ------------------------------------------------------------
# Initial Interfaces
# ------------------------------------------------------------

print("\n--- INITIAL INTERFACES ---")

for device_name in ["PC-01", "PC-02", "RUT-01"]:

    device = ncm.get_device(device_name)

    print(
        f"\n{device_name}:"
    )

    for interface in ncm.get_interfaces(device_name):

        print(interface)


# ------------------------------------------------------------
# GET INTERFACE
# ------------------------------------------------------------

print("\n--- GET INTERFACE ---")

print(
    ncm.get_interface(
        "PC-01",
        "eth0"
    )
)


# ------------------------------------------------------------
# ADD HOST INTERFACE
# ------------------------------------------------------------

print("\n--- ADD HOST INTERFACE ---")

pc1_eth1 = ncm.add_interface(
    "PC-01"
)

print(
    "Created:",
    pc1_eth1
)


# ------------------------------------------------------------
# ADD ROUTER INTERFACE
# ------------------------------------------------------------

print("\n--- ADD ROUTER INTERFACE ---")

router_eth2 = ncm.add_interface(
    "RUT-01"
)

print(
    "Created:",
    router_eth2
)


# ------------------------------------------------------------
# INTERFACES AFTER CREATION
# ------------------------------------------------------------

print("\n--- INTERFACES AFTER CREATION ---")

for device_name in ["PC-01", "RUT-01"]:

    print(f"\n{device_name}:")

    for interface in ncm.get_interfaces(device_name):

        print(interface)


# ------------------------------------------------------------
# REMOVE HOST INTERFACE
# ------------------------------------------------------------

print("\n--- REMOVE HOST INTERFACE ---")

print(
    "Removed:",
    ncm.remove_interface(
        "PC-01",
        pc1_eth1
    )
)


# ------------------------------------------------------------
# REMOVE ROUTER INTERFACE
# ------------------------------------------------------------

print("\n--- REMOVE ROUTER INTERFACE ---")

print(
    "Removed:",
    ncm.remove_interface(
        "RUT-01",
        router_eth2
    )
)


# ------------------------------------------------------------
# FINAL INTERFACES
# ------------------------------------------------------------

print("\n--- FINAL INTERFACES ---")

for device_name in ["PC-01", "RUT-01"]:

    print(f"\n{device_name}:")

    for interface in ncm.get_interfaces(device_name):

        print(interface)

# ============================================================
# CONNECTED INTERFACE DELETION TEST
# ============================================================

print("\n=== CONNECTED INTERFACE DELETION TEST ===")

print("\n--- CONNECT PC-01 TO SW-01 ---")

sim.connect_host_to_switch(
    "PC-01",
    "SW-01"
)

print(
    ncm.get_interface(
        "PC-01",
        "eth0"
    )
)


print("\n--- ATTEMPT TO REMOVE CONNECTED INTERFACE ---")

try:

    ncm.remove_interface(
        "PC-01",
        "eth0"
    )

except ValueError as e:

    print("EXPECTED ERROR:", e)


print("\n--- VERIFY INTERFACE STILL EXISTS ---")

print(
    ncm.get_interface(
        "PC-01",
        "eth0"
    )
)


print("\n=== NCM INITIAL TEST COMPLETE ===")