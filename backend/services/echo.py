"""
RFC 862 Echo Protocol Implementation for CyberHazardLab.
Provides a receiver-only service daemon running on Port 7 (TCP and UDP).
Echoes any received datagram or byte stream back to the sender.
"""

from .base import ServiceDaemon
from backend.core.event import Event


class EchoServerDaemon(ServiceDaemon):
    """
    RFC 862 Echo Server Daemon.
    Listens on Port 7 (TCP/UDP).
    Accepts incoming data and sends back an identical copy.
    """

    def handle_tcp(self, payload, connection, packet):
        if payload is None:
            return None

        # Log Echo Request and Echo Reply events if connected to simulation network
        if connection and getattr(connection, "network", None):
            conn_net = connection.network
            payload_len = len(payload) if hasattr(payload, "__len__") else 0

            conn_net.add_event(Event(
                type="ECHO_REQUEST_RECEIVED",
                severity="INFO",
                source=packet.source_ip,
                destination=packet.destination_ip,
                protocol="TCP",
                port=7,
                metadata={
                    "bytes": payload_len,
                    "host": getattr(self.host, "name", "UNKNOWN"),
                    "payload_preview": str(payload)[:64]
                }
            ))

            conn_net.add_event(Event(
                type="ECHO_REPLY_SENT",
                severity="INFO",
                source=packet.destination_ip,
                destination=packet.source_ip,
                protocol="TCP",
                port=7,
                metadata={
                    "bytes": payload_len,
                    "host": getattr(self.host, "name", "UNKNOWN")
                }
            ))

        return payload

    def handle_udp(self, payload, connection, packet):
        if payload is None:
            return None

        if connection and getattr(connection, "network", None):
            conn_net = connection.network
            payload_len = len(payload) if hasattr(payload, "__len__") else 0

            conn_net.add_event(Event(
                type="ECHO_REQUEST_RECEIVED",
                severity="INFO",
                source=packet.source_ip,
                destination=packet.destination_ip,
                protocol="UDP",
                port=7,
                metadata={
                    "bytes": payload_len,
                    "host": getattr(self.host, "name", "UNKNOWN"),
                    "payload_preview": str(payload)[:64]
                }
            ))

            conn_net.add_event(Event(
                type="ECHO_REPLY_SENT",
                severity="INFO",
                source=packet.destination_ip,
                destination=packet.source_ip,
                protocol="UDP",
                port=7,
                metadata={
                    "bytes": payload_len,
                    "host": getattr(self.host, "name", "UNKNOWN")
                }
            ))

        return payload
