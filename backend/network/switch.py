from .frame import EthernetFrame
from .link import Link
from .switchport import SwitchPort
from ..core.event import Event
from ..core.interface import NetworkInterface
from .network import Network


class Switch:

    def __init__(self, name, network:Network):
        self.name = name
        self.ports = {}
        self.mac_table ={}
        self.network = network
        self.event_callback = self.network.add_event

    def add_event(self, event):
        if self.event_callback:
            self.event_callback(event)

    def connect(self, host, intf_name="eth0"):
        interface = None

        for intf in host.interfaces:
            if intf.name == intf_name:
                interface = intf
                break

        if interface is None:
            raise ValueError(
                f"{host.name} does not have interface {intf_name}"
            )

        port = self.add_port()

        link = Link(interface, port)

        self.network.add_link(link)

        port.connect_link(link)
        interface.connect_link(link)

        return port

    def learn(self, mac, port):
        self.mac_table[mac] = port

    def receive(self, frame: EthernetFrame, in_port):
        #print("swr")
        
        self.learn(
            frame.source_mac, in_port
        )

        self.add_event(Event(
            type="FRAME_RECEIVED",
            source=frame.source_mac,
            destination=frame.destination_mac,
            protocol="ETHERNET",
            port=in_port,
            metadata={
                "switch": self.name
            }
        ))

        out_ports = [
                port_num
                for port_num in self.ports
                if port_num != in_port
            ]

        if frame.destination_mac == "FF:FF:FF:FF:FF:FF":
            

            self.network.add_event(Event(
                    type="FRAME_BROADCAST",
                    source=frame.source_mac,
                    destination=frame.destination_mac,
                    protocol="ETHERNET",
                    port=None,
                    metadata={
                        "switch": self.name,
                        "in_port": in_port,
                        "out_ports": out_ports
                    }
                ))

            for port_num in out_ports:
                self.ports[port_num].send(frame)

            return {
                "action": "BROADCAST",
                "ports": out_ports
            }


        dest_port_num = self.mac_table.get(frame.destination_mac)

        if dest_port_num is None:

            self.add_event(Event(
            type="FRAME_FLOODED",
            source=frame.source_mac,
            destination=frame.destination_mac,
            protocol="ETHERNET",
            metadata={
                "switch": self.name,
                "in_port": in_port,
                "out_ports": out_ports
                }
            ))

            for port_num in out_ports:
                self.ports[port_num].send(frame)

            return {
            "action": "FLOOD",
            "ports": out_ports
            }



        if dest_port_num == in_port:
            self.add_event(Event(
            type="FRAME_DROPPED",
            source=frame.source_mac,
            destination=frame.destination_mac,
            protocol="ETHERNET",
            port=in_port,
            metadata={
                "switch": self.name,
                "reason": "DESTINATION_ON_SOURCE_PORT"
                }
            ))


            return {
                "action": "DROP",
                "reason": "DESTINATION_ON_SOURCE_PORT"
            }
            #continue
        #print(dest_port_num)


            
        
        self.add_event(Event(
        type="FRAME_FORWARDED",
        source=frame.source_mac,
        destination=frame.destination_mac,
        protocol="ETHERNET",
        metadata={
            "switch": self.name,
            "in_port": in_port,
            "out_port": dest_port_num
            }
        ))

        self.ports[dest_port_num].send(frame)
        

        return {
            "action": "FORWARD",
            "ports": dest_port_num
        }

    def connect_switch(self, other_switch):
        local_port = self.add_port(mode="trunk")
        remote_port = other_switch.add_port(mode="trunk")

        link = Link(local_port, remote_port)

        self.network.add_link(link)

        local_port.connect_link(link)  # To SwitchPort
        remote_port.connect_link(link) # To SwitchPort 

        return local_port, remote_port

    def connect_router(self, rut_intf: NetworkInterface):
        port_num = len(self.ports) + 1

        port = SwitchPort(
            self,
            port_num,
            mode="trunk"
        )

        link = Link(rut_intf, port)

        self.network.add_link(link)

        port.connect_link(link)
        rut_intf.connect_link(link)

        self.ports[port_num] = port

        return port

    def add_port(self, mode="access"):
        port_num = len(self.ports) + 1

        port = SwitchPort( self, port_num, mode )

        self.ports[port_num] = port

        return port

    def remove_port(self, port_number):
        port = self.ports.get(port_number)
    
        if port is None:
            raise ValueError(
                f"Switch {self.name} does not have port {port_number}"
            )
    
        if port.link is not None:
            raise ValueError(
                f"Cannot remove Port-{port_number}: "
                "port is connected to a link"
            )
    
        return self.ports.pop(port_number)
        








    #don't need
    def forward(self, frame: EthernetFrame, port):

        if port not in self.ports:
            raise ValueError(f"Switch port {port} doesn't exist.")


        connection = self.ports[port]

        host = connection["host"]
        interface = connection["interface"]

        if interface.mac != frame.destination_mac:
            raise ValueError( f"Destination MAC {frame.destination_mac} does not match target interface MAC {interface.mac}")


        return host