from .base import ServiceDaemon
from backend.network.packet import UDPPacket, Packet
from backend.network.dhcp_packet import DHCPMessage, OPT_RELAY_AGENT
from backend.core.event import Event

class DHCPRelayDaemon(ServiceDaemon):
    def handle_udp(self, payload, connection, packet):
        # Locate relay service configuration
        relay_service = None
        for s in self.host.services:
            if s.name.upper() == "DHCP_RELAY" and s.status.lower() == "running":
                relay_service = s
                break

        if not relay_service:
            return None
        target_server_ip = relay_service.config.get("target_ip")
        if not target_server_ip:
            return None

        # 1. Structured DHCPMessage processing
        if isinstance(payload, DHCPMessage):
            msg = payload

            # Client -> Server (BOOTREQUEST: DISCOVER or REQUEST)
            if msg.op == 1:
                # Loop prevention
                if msg.hops >= 16:
                    return None

                # Determine which local interface received this request
                in_intf = getattr(packet, "in_interface", None)
                if not in_intf:
                    for i in self.host.interfaces:
                        if i.ip and i.ip != "0.0.0.0":
                            in_intf = i
                            break

                if not in_intf:
                    return None

                # If the inbound interface is on the same subnet as the target DHCP server,
                # the client and DHCP server are already on the same broadcast domain. Do not relay!
                if in_intf.subnet and in_intf.subnet not in ("0.0.0.0/0", "0.0.0.0"):
                    try:
                        import ipaddress
                        net = ipaddress.IPv4Network(in_intf.subnet, strict=False)
                        if ipaddress.IPv4Address(target_server_ip) in net:
                            return None
                    except Exception:
                        pass

                msg.giaddr = in_intf.ip
                msg.set_option(OPT_RELAY_AGENT, in_intf.ip)
                msg.hops += 1

                udp = UDPPacket(source_port=67, destination_port=67, payload=msg)
                fwd_pkt = Packet(
                    source_ip=in_intf.ip,
                    destination_ip=target_server_ip,
                    protocol="UDP",
                    payload=udp
                )

                if self.host.network:
                    self.host.network.add_event(Event(
                        type="DHCP_RELAY_FORWARD",
                        severity="INFO",
                        source=self.host.name,
                        destination=target_server_ip,
                        protocol="DHCP",
                        metadata={"action": "forward_discover", "client": packet.source_ip}
                    ))

                self.host.send_ip_packet(fwd_pkt)
                return None

            # Server -> Client (BOOTREPLY: OFFER or ACK)
            elif msg.op == 2:
                relay_ip = msg.giaddr if (msg.giaddr and msg.giaddr != "0.0.0.0") else msg.get_option(OPT_RELAY_AGENT)
                target_intf = next((i for i in self.host.interfaces if i.ip == relay_ip), self.host.interfaces[0] if self.host.interfaces else None)

                if not target_intf:
                    return None

                udp = UDPPacket(source_port=67, destination_port=68, payload=msg)
                broadcast_pkt = Packet(
                    source_ip=target_intf.ip,
                    destination_ip="255.255.255.255",
                    protocol="UDP",
                    payload=udp
                )

                if self.host.network:
                    self.host.network.add_event(Event(
                        type="DHCP_RELAY_REPLY",
                        severity="INFO",
                        source=self.host.name,
                        destination="BROADCAST",
                        protocol="DHCP",
                        metadata={"action": "broadcast_reply"}
                    ))

                self.host.send_ip_packet(broadcast_pkt, out_interface=target_intf)
                return None

        return None
