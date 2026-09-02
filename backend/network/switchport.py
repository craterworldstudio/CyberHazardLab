class SwitchPort:

    def __init__(self, switch, port_number, mode="access"):
        self.switch = switch
        self.port_number = port_number
        self.link = None
        self.mode = mode

    def connect_link(self, link):
        self.link =  link

    def receive(self, frame):
        #print('spr1')
        if self.switch is None:
            raise ValueError(
                f"This SwitchPort {self.port_number} is not connected to assigned to a switch"
            )
        return self.switch.receive( frame, self.port_number)
        
    def send(self, frame):
        #print('spr2')
        if self.link is None:
            raise ValueError(
                f"Switch port {self.port_number} is not connected to a link"
            )
        self.link.transmit(frame, self)

    def __repr__(self):
        # Checks if the port belongs to a parent Switch (e.g., "SW-01")
        switch_name = getattr(getattr(self, 'owner', None), 'name', None) or getattr(getattr(self, 'switch', None), 'name', 'Switch')

        return f"{switch_name}:Port-{self.port_number}"

    

