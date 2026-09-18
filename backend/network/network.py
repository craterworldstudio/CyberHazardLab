from ..core.host import Host
from ..core.event import Event
from .arp import ARP
import ipaddress
from .frame import EthernetFrame

class Network:

	def __init__(
				self, 
				name: str,
				subnet: str | None = None, 
				gateway: str | None = None 
				):
		
		self.name = name

		self.hosts : dict[str, Host] = {}
		self.events : list[Event] = []
		self.links = []
		self.subnets = {}
		from .arp import ARP
		self.arp = ARP(network=self)
		if subnet:
			self.add_subnet(subnet, gateway)

	def add_subnet(self, subnet: str, gateway: str | None = None):
		self.subnets[subnet] = {"gateway": gateway}
		return subnet

		#self.arp = ARP(self)

	def add_host(self, host: Host):
		host.network = self
		self.hosts[host.name] = host

	def add_event(self, event: Event):
		self.events.append(event)
		print(event)
		if getattr(self, "on_event", None):
			self.on_event(event)

	def connect(self, source:Host, destination:Host, protocol:str, port:int):
		src_ip = source.get_ip()
		dst_ip = destination.get_ip()

		if src_ip is None:
			raise ValueError(f"{source.name} does not have an IP address")

		if dst_ip is None:
			raise ValueError(f"{destination.name} does not have an IP address")

		if source.name not in self.hosts:
			raise ValueError(f"{source.name} is not part of this network")

		if destination.name not in self.hosts:
			raise ValueError(f"{destination.name} is not part of this network")
		intf = source.interfaces[0]
		dest_mac = intf.arp.resolve(intf, dst_ip)

		if dest_mac is None:
			self.add_event(Event(
				type = 'NETWORK_CONNECTION',
				source=src_ip,
				severity="WARNING",
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
				severity="INFO",
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

	def get_service_by_port(self, host: Host, protocol: str, port: int):
		for service in host.services:
			if (
				service.protocol.upper() == protocol.upper()
				and service.port == port
			):
				return service

		return None

	def add_service(self, host, service):
		if getattr(host, 'network', None) != self:
			raise ValueError(f"{host.name} is not part of this network")

		if self.get_services(host, service.name):
			raise ValueError(
				f"{host.name} already has service {service.name}"
			)

		service.status = "created"
		host.add_service(service)

		self.add_event(Event(
			type="SERVICE_CREATED",
            severity="INFO",
			source="SYSTEM",
			destination=getattr(host, "name", "UNKNOWN"),
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
		if hasattr(host, 'get_service_daemon'):
			daemon = host.get_service_daemon(service.name)
			if daemon and hasattr(daemon, 'on_start'):
				daemon.on_start(service)

		self.add_event(Event(
				type="SERVICE_STARTED",
                severity="INFO",
				source="SYSTEM",
				destination=getattr(host, "name", "UNKNOWN"),
				protocol=service.protocol,
				port=service.port,
				metadata={
					"host": host.name,
					"service": service.name
				}
			))
		
	def remove_service(self, host: Host, service_name: str):
		service = self.get_services(host, service_name)
		if service is None:
			raise ValueError(f"{host.name} does not have service {service_name}")
		
		host.services.remove(service)
		
		self.add_event(Event(
			type="SERVICE_REMOVED",
            severity="INFO",
			source="SYSTEM",
			destination=getattr(host, "name", "UNKNOWN"),
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
		if hasattr(host, 'get_service_daemon'):
			daemon = host.get_service_daemon(service.name)
			if daemon and hasattr(daemon, 'on_stop'):
				daemon.on_stop(service)

		self.add_event(Event(
				type="SERVICE_STOPPED",
                severity="INFO",
				source="SYSTEM",
				destination=getattr(host, "name", "UNKNOWN"),
				protocol=service.protocol,
				port=service.port,
				metadata={
					"host": host.name,
					"service": service.name
				}
			))

	def add_link(self, link):
		if link in self.links:
			return
		self.links.append(link)

	def remove_link(self, link):
		if link not in self.links:
			raise ValueError("Link is not registered in the network")

		self.links.remove(link)













	# NO LONGER NEEDED.
	def transmit_frame(self, frame: EthernetFrame, destination: Host):

		dest_intf = destination.interfaces[0]

		if frame.destination_mac != dest_intf.mac:
			self.add_event(Event(
				type="FRAME_DROPPED",
                severity="HIGH",
				source=frame.source_mac,
				destination=frame.destination_mac,
				protocol="ETHERNET",
				metadata={
					"reason": "DESTINATION_MAC_MISMATCH"
				}
			))

			return False


		self.add_event(Event(
				type="FRAME_DELIVERED",
                severity="INFO",
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

