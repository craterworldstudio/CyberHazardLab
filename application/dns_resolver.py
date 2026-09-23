import ipaddress
import time
from backend.network.packet import UDPPacket, Packet

def resolve_hostname(device, hostname, timeout=0.3):
    try:
        ipaddress.ip_address(hostname)
        return hostname # already an IP
    except ValueError:
        pass
        
    dns_ip = getattr(device, "dns_server", None)
    if not dns_ip:
        return None
        
    if not device.interfaces:
        return None
        
    intf = device.interfaces[0]
    
    udp = UDPPacket(source_port=53535, destination_port=53, payload=hostname)
    pkt = Packet(
        source_ip=intf.ip,
        destination_ip=dns_ip,
        protocol="UDP",
        payload=udp,
        ttl=64
    )
    
    device.last_dns_result = None
    device.send_ip_packet(pkt, out_interface=intf)
    
    start_wait = time.time()
    while time.time() - start_wait < timeout:
        if hasattr(device, "last_dns_result") and device.last_dns_result is not None:
            break
        time.sleep(0.01)
        
    res = getattr(device, "last_dns_result", None)
    if res and res.startswith("DNS_RESPONSE"):
        parts = res.split("->")
        if len(parts) == 2:
            return parts[1].strip()
            
    return None
