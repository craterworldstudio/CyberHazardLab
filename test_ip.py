from backend.state.manager import StateManager
import ipaddress
sm = StateManager(None)
print(sm.serialize_value(ipaddress.ip_network("10.0.0.0/24")))
