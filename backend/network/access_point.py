from .switch import Switch

class AccessPoint(Switch):
    def __init__(self, name, network=None):
        super().__init__(name, network)
        self.is_wireless = True
