class Link:

    def __init__(self, endpointA, endpointB):
        self.endpointA = endpointA
        self.endpointB = endpointB

    def other_end(self, endpoint):

        if endpoint == self.endpointA:
            return self.endpointB

        if endpoint == self.endpointB:
            return self.endpointA

        raise ValueError("Endpoint is not connected to this link")

    def transmit(self, frame, sender):
        #print("t1")
        receiver = self.other_end(sender)
        return receiver.receive(frame)    #TO SwitchPort

    def __repr__(self):
        def format_endpoint(ep):
            if ep is None:
                return "Disconnected"
            
            # If the endpoint is an interface/port belonging to a device
            owner_name = getattr(getattr(ep, 'owner', None), 'name', None)
            ep_name = getattr(ep, 'name', str(ep))
            
            if owner_name:
                return f"{owner_name}:{ep_name}"
            return ep_name

        return f"Link({format_endpoint(self.endpointA)} <---> {format_endpoint(self.endpointB)})"

    