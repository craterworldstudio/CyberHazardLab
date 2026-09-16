from backend.orchestrator import Simulation
from application.ncm.ncm import NetworkConfigurationManager
from application.ntm.ntm import NetworkTopologyManager
from backend.state.manager import StateManager
from application.api import API
import json

sim = Simulation()
sim.add_host("H1")
h1 = sim.hosts["H1"]
h1.add_interface("eth0")

ntm = NetworkTopologyManager(sim)
ncm = NetworkConfigurationManager(sim)
state = StateManager(sim)
api = API(ntm, ncm, state)

intf = ncm.get_interface("H1", "eth0")
print("Before:", getattr(intf, "status", "N/A"))
intf.status = "down"
print("After:", getattr(intf, "status", "N/A"))

print("Serialized:", json.dumps(api._serialize_device(h1), indent=2))
