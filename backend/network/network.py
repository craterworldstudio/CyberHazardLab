from ..core.host import Host
from ..core.event import Event
from .arp import ARP
import ipaddress
from .frame import EthernetFrame
import time

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

	def get_host(self, name_or_ip: str):
		if name_or_ip in self.hosts:
			return self.hosts[name_or_ip]
		return self.get_host_by_ip(name_or_ip)

	def get_host_by_ip(self, ip: str):
		for host in self.hosts.values():
			for intf in getattr(host, "interfaces", []):
				if intf.ip == ip:
					return host
		if hasattr(self, "orchestrator") and self.orchestrator:
			for router in self.orchestrator.routers.values():
				for intf in router.interfaces:
					if intf.ip == ip:
						return router
		return None

	def get_route(self, source, destination_ip: str):
		if hasattr(source, "lookup_route"):
			route = source.lookup_route(destination_ip)
			if route:
				return route, route.get("interface")
		for intf in getattr(source, "interfaces", []):
			if intf.subnet and intf.ip:
				try:
					net = ipaddress.ip_network(intf.subnet, strict=False)
					if ipaddress.ip_address(destination_ip) in net:
						return {"destination": net, "interface": intf, "next_hop": None}, intf
				except Exception:
					pass
		return None, None

	def add_event(self, event: Event):
		self.events.append(event)
		print(event)
		if getattr(self, "on_event", None):
			self.on_event(event)

		# Do NOT route switch-level frame forwarding or router packet forwarding into host logs (avoids packet storms)
		if event.type in (
			"FRAME_RECEIVED", "FRAME_FORWARDED", "FRAME_SENT",
			"PACKET_RECEIVED", "PACKET_FORWARDED", "PACKET_SENT", "PACKET_ROUTED"
		) or getattr(event, "port", None) in (514, 51400):
			return

		if hasattr(self, "hosts") and isinstance(self.hosts, dict):
			src_dev = self.hosts.get(event.source)
			if not src_dev and hasattr(self, "get_host_by_ip"):
				src_ip = str(event.source).split(":")[0] if event.source else ""
				src_dev = self.get_host_by_ip(src_ip)
			dst_dev = self.hosts.get(event.destination)
			if not dst_dev and hasattr(self, "get_host_by_ip"):
				dst_ip = str(event.destination).split(":")[0] if event.destination else ""
				dst_dev = self.get_host_by_ip(dst_ip)
			if src_dev and hasattr(src_dev, "log_event"):
				src_dev.log_event(event)
			if dst_dev and hasattr(dst_dev, "log_event") and dst_dev != src_dev:
				dst_dev.log_event(event)

			# Ensure active SIEM Collector daemon receives security events across network
			sim = getattr(self, "orchestrator", None)
			if sim and not getattr(event, "type", "").startswith("FRAME_") and getattr(event, "port", None) not in (514, 51400):
				# Host-internal events (commands, process execution, local login) require an active SIEM_AGENT on the source device
				if event.type in ("COMMAND_EXECUTED", "LOCAL_LOGIN", "PROCESS_CREATED", "PROCESS_STARTED", "ROOT_LOGIN"):
					has_agent = False
					if src_dev and hasattr(src_dev, "daemons") and isinstance(src_dev.daemons, dict):
						for d_name in ("SIEM_AGENT", "SIEM-AGENT"):
							ag = src_dev.daemons.get(d_name)
							if ag and getattr(ag, "is_running", False):
								has_agent = True
								break
					if not has_agent:
						return

				collector_daemon = getattr(self, "_soc_collector", None)
				if not collector_daemon or not getattr(collector_daemon, "is_running", False):
					collector_daemon = None
					for h in list(sim.hosts.values()) + list(sim.routers.values()):
						if hasattr(h, "daemons") and isinstance(h.daemons, dict):
							for d_name in ("SIEM_COLLECTOR", "SIEM-COLLECTOR", "SIEM"):
								cd = h.daemons.get(d_name)
								if cd and getattr(cd, "is_running", False):
									collector_daemon = cd
									self._soc_collector = cd
									break
						if collector_daemon:
							break
				if collector_daemon and hasattr(collector_daemon, "ingest_event"):
					collector_daemon.ingest_event({
						"id": f"ev-{event.type.lower()}-{int(time.time()*1000)}",
						"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
						"host": getattr(dst_dev, "name", str(event.destination)),
						"type": event.type,
						"severity": getattr(event, "severity", "INFO"),
						"source": str(event.source),
						"destination": str(event.destination),
						"protocol": getattr(event, "protocol", "IP"),
						"port": getattr(event, "port", None),
						"metadata": getattr(event, "metadata", {}) or {}
					})

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

	def start_service(self, host: Host, service_name: str, force: bool = False):

		service = self.get_services(host, service_name)

		if service is None:
			raise ValueError(
				f"{host.name} does not have service {service_name}"
			)

		if service.status == "running" and not force:
			return

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

