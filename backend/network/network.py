from ..core.host import Host
from ..core.event import Event
from .arp import ARP
import ipaddress
from .frame import EthernetFrame

class Network:

	def __init__(
				self, 
				name: str,
				#subnet: str, 
				#gateway: str | None 
				):
		
		self.name = name

		self.hosts : dict[str, Host] = {}
		self.events : list[Event] = []

		#self.subnet = [ipaddress.ip_network(subnet)]
		self.subnets = {}
		#self.gateway = gateway

		#self.arp = ARP(self)

	def add_subnet(self, subnet, gateway):
		network = ipaddress.ip_network(subnet)

		if network in self.subnets:
			raise ValueError(
				f"Subnet already exists: {network}"
			)

		self.subnets[network] = {
			"gateway": gateway
		}

	def get_subnet(self, ip):
		ip = ipaddress.ip_address(ip)

		for subnet, config in self.subnets.items():
			if ip in subnet:
				return subnet

		return None

	def get_gateway(self, ip):
		subnet = self.get_subnet(ip)

		if subnet is None:
			return None

		return self.subnets[subnet]["gateway"]

	def add_host(self, host: Host):

		for interface in host.interfaces:

			if interface.ip is None:
				continue

			subnet = self.get_subnet(interface.ip)

			if subnet is None:
				raise ValueError(
					f"{interface.ip} does not belong to any subnet"
				)

			

		self.hosts[host.get_ip()] = host

	def add_event(self, event: Event):
			self.events.append(event)

	def connect(self, source:Host, destination:Host, protocol:str, port:int):
		src_ip = source.get_ip()
		dst_ip = destination.get_ip()

		if src_ip is None:
			raise ValueError(f"{source.name} does not have an IP address")

		if dst_ip is None:
			raise ValueError(f"{destination.name} does not have an IP address")

		if src_ip not in self.hosts:
			raise ValueError(f"{source.name} is not part of this network")

		if dst_ip not in self.hosts:
			raise ValueError(f"{destination.name} is not part of this network")
		intf = source.interfaces[0]
		dest_mac = intf.arp.resolve(intf, dst_ip)

		if dest_mac is None:
			self.add_event(Event(
				type = 'NETWORK_CONNECTION',
				source=src_ip,
				destination=dst_ip,
				protocol=protocol.upper(),
				port = port,
				metadata={
					   "src_host": source.name,
					   "dst_host": destination.name,
					   "result": "FAILED",
					   "reason": "ARP_FAILED"
					}
				))

			return "ARP_FAILED"

		service = None

		for candidate in destination.services:

			if (
				candidate.protocol.upper() == protocol.upper()
				and candidate.port == port
			):
				service = candidate
				break


		if service is None:
			result = "REFUSED"
			reason = "PORT_CLOSED"

		elif service.status.lower() != "running":
			result = "REFUSED"
			reason = "SERVICE_STOPPED"

		else:
			result = "ACCEPTED"
			reason = "SERVICE_AVAILABLE"

		self.add_event( Event(
				type = 'NETWORK_CONNECTION',
				source=src_ip,
				destination=dst_ip,
				protocol=protocol.upper(),
				port = port,
				metadata={
					   "src_host": source.name,
					   "dst_host": destination.name,
					   "dst_mac": dest_mac,
					   "result": result,
					   "reason": reason
					}
				)
			)

		return result

	def get_services(self, host: Host, service_name: str):

		for service in host.services:
				if service.name.lower() == service_name.lower():
					return service

		return None

	def add_service(self, host: Host, service):
		if host.get_ip() not in self.hosts:
			raise ValueError(f"{host.name} is not part of this network")

		if self.get_services(host, service.name):
			raise ValueError(
				f"{host.name} already has service {service.name}"
			)

		service.status = "created"
		host.add_service(service)

		self.add_event(Event(
			type="SERVICE_CREATED",
			source="SYSTEM",
			destination=host.get_ip(),
			protocol=service.protocol,
			port=service.port,
			metadata={
				"host": host.name,
				"service": service.name,
				"status": service.status
			}
		))

	def start_service(self, host: Host, service_name: str):

		service = self.get_services(host, service_name)

		if service is None:
			raise ValueError(
				f"{host.name} does not have service {service_name}"
			)

		if service.status == "running": return

		service.status = "running"

		self.add_event(Event(
					type="SERVICE_STARTED",
					source="SYSTEM",
					destination=host.get_ip(),
					protocol=service.protocol,
					port=service.port,
					metadata={
						"host": host.name,
						"service": service.name
					}
				))
		
	def stop_services(self, host: Host, service_name: str):

		service = self.get_services(host, service_name)
		
		
		if service is None:
			raise ValueError(
				f"{host.name} does not have service {service_name}"
			)

		if service.status == "stopped": return

		service.status = "stopped"

		self.add_event(Event(
						type="SERVICE_STOPPED",
						source="SYSTEM",
						destination=host.get_ip(),
						protocol=service.protocol,
						port=service.port,
						metadata={
							"host": host.name,
							"service": service.name
						}
					))

















	# NO LONGER NEEDED.
	def transmit_frame(self, frame: EthernetFrame, destination: Host):

		dest_intf = destination.interfaces[0]

		if frame.destination_mac != dest_intf.mac:
			self.add_event(
			Event(
				type="FRAME_DROPPED",
				source=frame.source_mac,
				destination=frame.destination_mac,
				protocol="ETHERNET",
				metadata={
					"reason": "DESTINATION_MAC_MISMATCH"
				}
			))

			return False


		self.add_event(
			Event(
				type="FRAME_DELIVERED",
				source=frame.source_mac,
				destination=frame.destination_mac,
				protocol="ETHERNET",
				metadata={
					"source_ip": frame.payload.source_ip,
					"destination_ip": frame.payload.destination_ip,
					"protocol": frame.payload.protocol,
				}
			))

		return True

