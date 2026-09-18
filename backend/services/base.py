class ServiceDaemon:
    def __init__(self, host):
        self.host = host

    def on_start(self, service_model):
        """Called when the service is started in the UI"""
        pass

    def on_stop(self, service_model):
        """Called when the service is stopped in the UI"""
        pass

    def handle_tcp(self, payload, connection, packet):
        """
        Process incoming TCP payload.
        Should return a string payload to respond with, or None.
        """
        return None

    def handle_udp(self, payload, connection, packet):
        """
        Process incoming UDP payload.
        Should return a string payload to respond with, or None.
        """
        return None
