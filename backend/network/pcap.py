import struct
import socket
import time
from typing import Any

def calc_checksum(data: bytes) -> int:
    if len(data) % 2 == 1:
        data += b'\x00'
    s = sum(struct.unpack(f'!{len(data)//2}H', data))
    while (s >> 16):
        s = (s & 0xffff) + (s >> 16)
    return (~s) & 0xffff

def mac_to_bytes(mac_str: str | None) -> bytes:
    if not mac_str or mac_str.lower() in ("ff:ff:ff:ff:ff:ff", "broadcast"):
        return b'\xff\xff\xff\xff\xff\xff'
    clean = mac_str.replace(":", "").replace("-", "").replace(".", "").strip()
    try:
        return bytes.fromhex(clean.ljust(12, '0')[:12])
    except Exception:
        return b'\x00\x00\x00\x00\x00\x00'

def ip_to_bytes(ip_str: str | None) -> bytes:
    if not ip_str:
        return b'\x00\x00\x00\x00'
    try:
        clean = ip_str.split("/")[0].strip()
        return socket.inet_aton(clean)
    except Exception:
        return b'\x00\x00\x00\x00'

def encode_domain_name(domain: str) -> bytes:
    parts = domain.strip().split(".")
    out = b""
    for p in parts:
        if not p: continue
        b = p.encode('utf-8', errors='ignore')
        out += bytes([len(b)]) + b
    out += b'\x00'
    return out

class PCAPWriter:
    GLOBAL_HEADER = struct.pack('<IHHiIII', 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1)

    @classmethod
    def frame_to_bytes(cls, frame) -> bytes:
        if not frame:
            return b""

        dst_mac = mac_to_bytes(getattr(frame, "destination_mac", "FF:FF:FF:FF:FF:FF"))
        src_mac = mac_to_bytes(getattr(frame, "source_mac", "00:00:00:00:00:00"))
        payload = getattr(frame, "payload", None)

        if not payload:
            return dst_mac + src_mac + struct.pack('!H', 0x0800) + (b'\x00' * 46)

        # Check for ARP
        if payload.__class__.__name__ == "ARPPacket":
            ethertype = 0x0806
            opcode = 1 if getattr(payload, "operation", "REQUEST").upper() in ("REQUEST", "1") else 2
            sender_mac = mac_to_bytes(getattr(payload, "sender_mac", None))
            sender_ip = ip_to_bytes(getattr(payload, "sender_ip", None))
            target_mac = mac_to_bytes(getattr(payload, "target_mac", None))
            target_ip = ip_to_bytes(getattr(payload, "target_ip", None))
            arp_body = struct.pack('!HHBBH', 1, 0x0800, 6, 4, opcode) + sender_mac + sender_ip + target_mac + target_ip
            eth_frame = dst_mac + src_mac + struct.pack('!H', ethertype) + arp_body
            if len(eth_frame) < 60:
                eth_frame += b'\x00' * (60 - len(eth_frame))
            return eth_frame

        # IPv4 Packet
        ethertype = 0x0800
        src_ip = ip_to_bytes(getattr(payload, "source_ip", "0.0.0.0"))
        dst_ip = ip_to_bytes(getattr(payload, "destination_ip", "0.0.0.0"))
        proto_name = getattr(payload, "protocol", "IP").upper()
        l4_payload = getattr(payload, "payload", None)

        proto_num = 0
        l4_bytes = b""

        if proto_name == "ICMP" or l4_payload.__class__.__name__ == "ICMPPacket":
            proto_num = 1
            icmp_type_str = str(getattr(l4_payload, "type", "ECHO_REQUEST")).upper()
            icmp_code = int(getattr(l4_payload, "code", 0))
            if "REPLY" in icmp_type_str:
                icmp_type = 0
            elif "REQUEST" in icmp_type_str:
                icmp_type = 8
            elif "UNREACHABLE" in icmp_type_str:
                icmp_type = 3
            elif "TIME_EXCEEDED" in icmp_type_str:
                icmp_type = 11
            else:
                icmp_type = 8

            data_str = getattr(l4_payload, "payload", "ping")
            data_bytes = data_str.encode('utf-8') if isinstance(data_str, str) else bytes(data_str or b'')
            # ICMP Header: Type(1), Code(1), Checksum(2), Id(2), Seq(2)
            icmp_hdr_no_cksum = struct.pack('!BBHHH', icmp_type, icmp_code, 0, 1, 1) + data_bytes
            cksum = calc_checksum(icmp_hdr_no_cksum)
            l4_bytes = struct.pack('!BBHHH', icmp_type, icmp_code, cksum, 1, 1) + data_bytes

        elif proto_name == "UDP" or l4_payload.__class__.__name__ == "UDPPacket":
            proto_num = 17
            src_port = int(getattr(l4_payload, "source_port", 0))
            dst_port = int(getattr(l4_payload, "destination_port", 0))
            udp_data = getattr(l4_payload, "payload", b"")

            # Check if DHCP
            if udp_data.__class__.__name__ == "DHCPMessage":
                msg = udp_data
                op = getattr(msg, "op", 1)
                htype = getattr(msg, "htype", 1)
                hlen = getattr(msg, "hlen", 6)
                hops = getattr(msg, "hops", 0)
                xid = getattr(msg, "xid", 0x12345678)
                secs = getattr(msg, "secs", 0)
                flags = getattr(msg, "flags", 0)
                ciaddr = ip_to_bytes(getattr(msg, "ciaddr", "0.0.0.0"))
                yiaddr = ip_to_bytes(getattr(msg, "yiaddr", "0.0.0.0"))
                siaddr = ip_to_bytes(getattr(msg, "siaddr", "0.0.0.0"))
                giaddr = ip_to_bytes(getattr(msg, "giaddr", "0.0.0.0"))
                chaddr_raw = mac_to_bytes(getattr(msg, "chaddr", "00:00:00:00:00:00")) + (b'\x00' * 10)
                sname = b'\x00' * 64
                file_field = b'\x00' * 128
                magic_cookie = struct.pack('!BBBB', 99, 130, 83, 99)

                # Format options
                opt_bytes = b""
                msg_type_str = str(getattr(msg, "message_type", "")).upper()
                msg_type_map = {
                    "DHCPDISCOVER": 1, "DHCPOFFER": 2, "DHCPREQUEST": 3,
                    "DHCPDECLINE": 4, "DHCPACK": 5, "DHCPNAK": 6, "DHCPRELEASE": 7
                }
                if msg_type_str in msg_type_map:
                    opt_bytes += struct.pack('!BBB', 53, 1, msg_type_map[msg_type_str])

                for code, val in getattr(msg, "options", {}).items():
                    if code == 53: continue
                    if isinstance(val, str) and "." in val:
                        ip_b = ip_to_bytes(val)
                        opt_bytes += struct.pack('!BB', code, len(ip_b)) + ip_b
                    elif isinstance(val, int):
                        if val > 65535:
                            opt_bytes += struct.pack('!BBI', code, 4, val)
                        else:
                            opt_bytes += struct.pack('!BBH', code, 2, val)
                    elif isinstance(val, str):
                        sb = val.encode('utf-8')
                        opt_bytes += struct.pack('!BB', code, len(sb)) + sb

                opt_bytes += b'\xff' # End option

                bootp = struct.pack('!BBBBIHH', op, htype, hlen, hops, xid, secs, flags)
                bootp += ciaddr + yiaddr + siaddr + giaddr + chaddr_raw + sname + file_field + magic_cookie + opt_bytes
                raw_payload = bootp

            # Check if DNS query or response
            elif src_port == 53 or dst_port == 53:
                payload_str = str(udp_data)
                is_response = (src_port == 53)
                tx_id = 0x5353
                flags = 0x8180 if is_response else 0x0100

                if is_response and "->" in payload_str:
                    parts = payload_str.replace("DNS_RESPONSE:", "").split("->")
                    query_name = parts[0].strip()
                    resolved_ip = parts[1].strip()
                    qname_bytes = encode_domain_name(query_name)
                    dns_hdr = struct.pack('!HHHHHH', tx_id, flags, 1, 1, 0, 0)
                    question = qname_bytes + struct.pack('!HH', 1, 1)
                    answer = struct.pack('!HHHIH', 0xc00c, 1, 1, 300, 4) + ip_to_bytes(resolved_ip)
                    raw_payload = dns_hdr + question + answer
                else:
                    clean_name = payload_str.replace("DNS_RESPONSE:", "").replace("DNS_NXDOMAIN:", "").strip().split()[0]
                    qname_bytes = encode_domain_name(clean_name or "local")
                    ancount = 0
                    if "NXDOMAIN" in payload_str:
                        flags = 0x8183
                    dns_hdr = struct.pack('!HHHHHH', tx_id, flags, 1, ancount, 0, 0)
                    question = qname_bytes + struct.pack('!HH', 1, 1)
                    raw_payload = dns_hdr + question
            else:
                raw_payload = udp_data.encode('utf-8') if isinstance(udp_data, str) else bytes(udp_data or b'')

            udp_len = 8 + len(raw_payload)
            l4_bytes = struct.pack('!HHHH', src_port, dst_port, udp_len, 0) + raw_payload

        elif proto_name == "TCP" or l4_payload.__class__.__name__ == "TCPPacket":
            proto_num = 6
            src_port = int(getattr(l4_payload, "source_port", 0))
            dst_port = int(getattr(l4_payload, "destination_port", 0))
            seq = int(getattr(l4_payload, "sequence_number", 0))
            ack = int(getattr(l4_payload, "acknowledgement_number", 0))
            flags_set = getattr(l4_payload, "flags", set())
            if isinstance(flags_set, (list, set, tuple)):
                flags_int = 0
                for f in flags_set:
                    f_u = str(f).upper()
                    if "FIN" in f_u: flags_int |= 0x01
                    if "SYN" in f_u: flags_int |= 0x02
                    if "RST" in f_u: flags_int |= 0x04
                    if "PSH" in f_u: flags_int |= 0x08
                    if "ACK" in f_u: flags_int |= 0x10
                    if "URG" in f_u: flags_int |= 0x20
            else:
                flags_int = int(flags_set or 0)

            tcp_data = getattr(l4_payload, "payload", b"")
            data_bytes = tcp_data.encode('utf-8') if isinstance(tcp_data, str) else bytes(tcp_data or b'')
            data_offset = 0x50
            l4_bytes = struct.pack('!HHIIBBHHH', src_port, dst_port, seq, ack, data_offset, flags_int, 64240, 0, 0) + data_bytes
        else:
            raw_p = getattr(payload, "payload", b"")
            l4_bytes = raw_p.encode('utf-8') if isinstance(raw_p, str) else bytes(raw_p or b'')

        total_len = 20 + len(l4_bytes)
        ttl = int(getattr(payload, "ttl", 64))
        ip_hdr_no_cksum = struct.pack('!BBHHHBBH', 0x45, 0, total_len, 0x1234, 0x4000, ttl, proto_num, 0) + src_ip + dst_ip
        ip_cksum = calc_checksum(ip_hdr_no_cksum)
        ip_hdr = struct.pack('!BBHHHBBH', 0x45, 0, total_len, 0x1234, 0x4000, ttl, proto_num, ip_cksum) + src_ip + dst_ip

        eth_frame = dst_mac + src_mac + struct.pack('!H', ethertype) + ip_hdr + l4_bytes
        if len(eth_frame) < 60:
            eth_frame += b'\x00' * (60 - len(eth_frame))
        return eth_frame

    @classmethod
    def build_pcap(cls, packets: list[tuple[float, Any]]) -> bytes:
        out = bytearray(cls.GLOBAL_HEADER)
        for ts, frame in packets:
            frame_bytes = cls.frame_to_bytes(frame)
            if not frame_bytes:
                continue
            ts_sec = int(ts)
            ts_usec = int((ts - ts_sec) * 1_000_000)
            pkt_len = len(frame_bytes)
            pkt_hdr = struct.pack('<IIII', ts_sec, ts_usec, pkt_len, pkt_len)
            out.extend(pkt_hdr)
            out.extend(frame_bytes)
        return bytes(out)
