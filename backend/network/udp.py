from .packet import UDPPacket
from backend.core.event import Event

class UDPConnection:

    def __init__(
        self,
        local_ip: str,
        local_port: int,
        remote_ip: str,
        remote_port: int,
        network
    ):
        self.local_ip = local_ip
        self.local_port = local_port

        self.remote_ip = remote_ip
        self.remote_port = remote_port

        self.network = network


    def send(self, data):

        packet = UDPPacket(
            source_port=self.local_port,
            destination_port=self.remote_port,
            payload=data
        )

        payload_length = (
            len(data)
            if data is not None
            else 0
        )

        self.network.add_event(Event(
            type="UDP_DATAGRAM_SENT",
            source=f"{self.local_ip}:{self.local_port}",
            destination=f"{self.remote_ip}:{self.remote_port}",
            protocol="UDP",
            port=self.remote_port,
            metadata={
                "bytes": payload_length
            }
        ))

        return packet

    def receive(self, packet: UDPPacket):

        payload_length = (
            len(packet.payload)
            if packet.payload is not None
            else 0
        )
    
        self.network.add_event(Event(
            type="UDP_DATAGRAM_RECEIVED",
            source=f"{self.remote_ip}:{self.remote_port}",
            destination=f"{self.local_ip}:{self.local_port}",
            protocol="UDP",
            port=self.local_port,
            metadata={
                "bytes": payload_length
            }
        ))
    
        return packet.payload