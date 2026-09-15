import json

with open("simulation_state.json", "r") as f:
    data = json.load(f)

if "RUT-01" in data["simulation"]["routes"]:
    del data["simulation"]["routes"]["RUT-01"]

with open("simulation_state.json", "w") as f:
    json.dump(data, f, indent=4)
