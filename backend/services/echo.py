from .base import ServiceDaemon

class EchoServerDaemon(ServiceDaemon):
    def handle_tcp(self, payload, connection, packet):
        return payload
        
    def handle_udp(self, payload, connection, packet):
        return payload
