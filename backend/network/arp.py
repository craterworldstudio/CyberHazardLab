from .packet import ARPPacket
from ..core.event import Event
from .frame import EthernetFrame

class ARP:
    """
    Standard ARP subsystem for a Node.
    Manages local ARP cache and pending packet transmission queue.
    """
    def __init__(self, node=None, network=None):
        self.node = node
        self._network = network
        self.cache: dict[str, str] = {}  # ip -> mac
        self.pending_queue: dict[str, list] = {}  # ip -> list of (packet, interface)

    @property
    def network(self):
        if self._network:
            return self._network
        return getattr(self.node, "network", None)

    def resolve(self, a, b=None) -> str | None:
        """Lookup MAC in cache. If source interface provided and missing, fire request."""
        if b is not None:
            source_intf = a
            target_ip = b
        else:
            source_intf = None
            target_ip = a

        if target_ip in self.cache:
            return self.cache[target_ip]

        if source_intf:
            self.request(source_intf, target_ip)

        return None

    def request(self, interface, target_ip: str):
        """Send an ARP request out the given interface."""
        if hasattr(interface, "interfaces") and interface.interfaces:
            interface = interface.interfaces[0]
        req = ARPPacket(
            operation="REQUEST",
            sender_ip=interface.ip or "0.0.0.0",
            sender_mac=interface.mac,
            target_ip=target_ip
        )
        frame = EthernetFrame(
            source_mac=interface.mac,
            destination_mac="FF:FF:FF:FF:FF:FF",
            payload=req
        )
        if self.network:
            self.network.add_event(Event(
                type="ARP_REQUEST",
                severity="INFO",
                source=interface.ip or "0.0.0.0",
                destination=target_ip,
                protocol="ARP",
                metadata={"mac": interface.mac}
            ))
        if interface.link:
            interface.send(frame)

    def enqueue(self, target_ip: str, packet, interface):
        """Buffer a packet waiting for ARP resolution."""
        if target_ip not in self.pending_queue:
            self.pending_queue[target_ip] = []
        self.pending_queue[target_ip].append((packet, interface))

    def receive(self, interface, packet: ARPPacket):
        """Handle incoming ARP request or reply."""
        if packet.operation == "REQUEST":
            # Only reply if the target IP belongs to this interface
            if packet.target_ip == interface.ip and interface.ip not in (None, "0.0.0.0"):
                # Also learn sender MAC if valid IP
                if packet.sender_ip and packet.sender_ip != "0.0.0.0":
                    self.cache[packet.sender_ip] = packet.sender_mac

                reply = ARPPacket(
                    operation="REPLY",
                    sender_ip=interface.ip,
                    sender_mac=interface.mac,
                    target_ip=packet.sender_ip,
                    target_mac=packet.sender_mac
                )
                frame = EthernetFrame(
                    source_mac=interface.mac,
                    destination_mac=packet.sender_mac,
                    payload=reply
                )
                interface.send(frame)

        elif packet.operation == "REPLY":
            self.cache[packet.sender_ip] = packet.sender_mac
            if self.network:
                self.network.add_event(Event(
                    type="ARP_REPLY",
                    severity="INFO",
                    source=packet.sender_ip,
                    destination=packet.target_ip,
                    protocol="ARP",
                    metadata={"mac": packet.sender_mac}
                ))

            # Flush all pending packets waiting for this IP
            queued = self.pending_queue.pop(packet.sender_ip, [])
            for pkt, out_intf in queued:
                self.node.send_ip_packet(pkt, out_interface=out_intf)
