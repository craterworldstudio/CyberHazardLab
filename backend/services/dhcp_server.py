from .base import ServiceDaemon
from backend.network.packet import UDPPacket, Packet
from backend.network.dhcp_packet import (
    DHCPMessage, DHCPDISCOVER, DHCPOFFER, DHCPREQUEST, DHCPACK, DHCPNAK,
    OPT_MESSAGE_TYPE, OPT_SUBNET_MASK, OPT_ROUTER, OPT_LEASE_TIME, OPT_SERVER_ID, OPT_RELAY_AGENT, OPT_REQUESTED_IP
)
from backend.core.event import Event

class DHCPServerDaemon(ServiceDaemon):
    def _get_dhcp_manager(self):
        network = self.host.network
        if hasattr(network, "orchestrator") and hasattr(network.orchestrator, "dhcp"):
            return network.orchestrator.dhcp
        if hasattr(network, "dhcp"):
            return network.dhcp
        return None

    def handle_udp(self, payload, connection, packet):
        dhcp_mgr = self._get_dhcp_manager()
        if not dhcp_mgr:
            return None

        server_ip = self.host.interfaces[0].ip if self.host.interfaces else "0.0.0.0"

        # 1. Structured DHCPMessage
        if isinstance(payload, DHCPMessage):
            msg = payload

            # Determine subnet from giaddr or Option 82 or incoming interface
            relay_ip = msg.giaddr if (msg.giaddr and msg.giaddr != "0.0.0.0") else msg.get_option(OPT_RELAY_AGENT)
            if relay_ip:
                lookup_target = relay_ip
            else:
                lookup_target = self.host.interfaces[0].subnet if self.host.interfaces else "10.0.0.0/24"

            scope = dhcp_mgr.get_scope(lookup_target)
            if not scope:
                scope = dhcp_mgr.auto_provision_scope(lookup_target, default_gateway=relay_ip or server_ip)
            if not scope:
                return None

            # Apply any custom scope config defined on DHCP service
            dhcp_svc = next((s for s in getattr(self.host, "services", []) if s.name.upper() == "DHCP"), None)
            if dhcp_svc and getattr(dhcp_svc, "config", None):
                cfg = dhcp_svc.config
                if "gateway" in cfg and cfg["gateway"]:
                    scope.gateway = str(cfg["gateway"]).strip()
                if "dns" in cfg and cfg["dns"]:
                    scope.dns_server = str(cfg["dns"]).strip()
                if "domain_name" in cfg and cfg["domain_name"]:
                    scope.domain_name = str(cfg["domain_name"]).strip()
                if "lease_time" in cfg and cfg["lease_time"]:
                    try:
                        scope.lease_time = int(cfg["lease_time"])
                    except Exception:
                        pass
                if "pool_start" in cfg and "pool_end" in cfg and cfg["pool_start"] and cfg["pool_end"]:
                    try:
                        import ipaddress
                        scope.start_ip = ipaddress.IPv4Address(cfg["pool_start"])
                        scope.end_ip = ipaddress.IPv4Address(cfg["pool_end"])
                    except Exception:
                        pass

            if msg.message_type == DHCPDISCOVER:
                try:
                    offered_ip = scope.offer(msg.chaddr)
                except Exception:
                    return None

                reply = DHCPMessage(
                    op=2,
                    xid=msg.xid,
                    yiaddr=offered_ip,
                    siaddr=server_ip,
                    giaddr=msg.giaddr,
                    chaddr=msg.chaddr
                )
                reply.message_type = DHCPOFFER
                reply.set_option(OPT_SUBNET_MASK, str(scope.network.netmask))
                reply.set_option(OPT_ROUTER, scope.gateway)
                reply.set_option(OPT_LEASE_TIME, scope.lease_time)
                reply.set_option(OPT_SERVER_ID, server_ip)
                if msg.get_option(OPT_RELAY_AGENT):
                    reply.set_option(OPT_RELAY_AGENT, msg.get_option(OPT_RELAY_AGENT))

                dest_ip = relay_ip if relay_ip else "255.255.255.255"
                dest_port = 67 if relay_ip else 68

                udp = UDPPacket(source_port=67, destination_port=dest_port, payload=reply)
                resp_pkt = Packet(
                    source_ip=server_ip,
                    destination_ip=dest_ip,
                    protocol="UDP",
                    payload=udp
                )
                self.host.send_ip_packet(resp_pkt)
                return None

            elif msg.message_type == DHCPREQUEST:
                req_ip = msg.get_option(OPT_REQUESTED_IP) or (msg.yiaddr if (msg.yiaddr and msg.yiaddr != "0.0.0.0") else msg.ciaddr)
                dest_ip = relay_ip if relay_ip else "255.255.255.255"
                dest_port = 67 if relay_ip else 68

                if not req_ip or not scope.validate_lease(msg.chaddr, req_ip):
                    # RFC 2131: Send DHCPNAK if requested IP is invalid or unavailable
                    nak = DHCPMessage(
                        op=2,
                        xid=msg.xid,
                        siaddr=server_ip,
                        giaddr=msg.giaddr,
                        chaddr=msg.chaddr
                    )
                    nak.message_type = DHCPNAK
                    nak.set_option(OPT_SERVER_ID, server_ip)
                    if msg.get_option(OPT_RELAY_AGENT):
                        nak.set_option(OPT_RELAY_AGENT, msg.get_option(OPT_RELAY_AGENT))

                    udp = UDPPacket(source_port=67, destination_port=dest_port, payload=nak)
                    resp_pkt = Packet(
                        source_ip=server_ip,
                        destination_ip=dest_ip,
                        protocol="UDP",
                        payload=udp
                    )
                    self.host.send_ip_packet(resp_pkt)
                    return None

                # Lease valid and confirmed: Send DHCPACK
                reply = DHCPMessage(
                    op=2,
                    xid=msg.xid,
                    yiaddr=req_ip,
                    siaddr=server_ip,
                    giaddr=msg.giaddr,
                    chaddr=msg.chaddr
                )
                reply.message_type = DHCPACK
                reply.set_option(OPT_SUBNET_MASK, str(scope.network.netmask))
                reply.set_option(OPT_ROUTER, scope.gateway)
                reply.set_option(OPT_LEASE_TIME, scope.lease_time)
                reply.set_option(OPT_SERVER_ID, server_ip)
                if msg.get_option(OPT_RELAY_AGENT):
                    reply.set_option(OPT_RELAY_AGENT, msg.get_option(OPT_RELAY_AGENT))

                udp = UDPPacket(source_port=67, destination_port=dest_port, payload=reply)
                resp_pkt = Packet(
                    source_ip=server_ip,
                    destination_ip=dest_ip,
                    protocol="UDP",
                    payload=udp
                )
                self.host.send_ip_packet(resp_pkt)
                return None

        # 2. String conversion fallback
        return None
