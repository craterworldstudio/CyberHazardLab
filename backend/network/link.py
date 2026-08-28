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

    