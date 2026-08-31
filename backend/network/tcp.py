from enum import Enum
from .packet import TCPPacket
from backend.core.event import Event

class TCPState(Enum):
    
    LISTEN = "LISTEN"
    SYN_SENT = "SYN_SENT"
    SYN_RECEIVED = "SYN_RECEIVED"
    ESTABLISHED = "ESTABLISHED"

    FIN_WAIT1 = "FIN_WAIT1"
    FIN_WAIT2 = "FIN_WAIT2"
    CLOSE_WAIT = "CLOSE_WAIT"
    LAST_ACK = "LAST_ACK"
    TIME_WAIT = "TIME_WAIT"
    CLOSED = "CLOSED"

    RST = "RST"

class TCPConnection:

    def __init__(
        self,
        local_ip: str, local_port: int,
        remote_ip: str, remote_port: int,
        network
    ):
        self.local_ip = local_ip
        self.local_port = local_port

        self.remote_ip = remote_ip
        self.remote_port = remote_port

        self.state = TCPState.CLOSED

        self.sequence_number = 0
        self.acknowledgement_number = 0

        self.time_wait_remaining = None

        self.network = network

    # Helper method for consistent telemetry formatting
    def _log_event(self, event_type: str, flags: list, metadata: dict = None):
        if not self.network:
            return
        
        event_metadata = {
            "state": self.state.value,
            "seq": self.sequence_number,
            "ack": self.acknowledgement_number,
            "flags": flags
        }
        if metadata:
            event_metadata.update(metadata)

        self.network.add_event(
            event_type,
            f"{self.local_ip}:{self.local_port}",
            f"{self.remote_ip}:{self.remote_port}",
            "TCP",
            event_metadata
        )

    #client connect
    def connect(self):
        if self.state != TCPState.CLOSED:
            raise RuntimeError(
                f"Cannot connect from state {self.state.value}"
            )

        self.sequence_number = 1000

        packet = TCPPacket(
            source_port=self.local_port,
            destination_port=self.remote_port,
            sequence_number=self.sequence_number,
            acknowledgement_number=0,
            flags={"SYN"}
        )

        self.state = TCPState.SYN_SENT
        self._log_event("TCP_SYN_SENT", ["SYN"])

        return packet
 
    def receive(self, packet: TCPPacket):
        TIME_WAIT_DURATION = 60
        
        if "RST" in packet.flags:
            self.state = TCPState.CLOSED
            self._log_event("TCP_RESET_RECEIVED", ["RST"])
            return None

        elif self.state == TCPState.LISTEN:

            if "SYN" in packet.flags and "ACK" not in packet.flags:

                self.acknowledgement_number = packet.sequence_number + 1
                self.sequence_number = 5000

                self.state = TCPState.SYN_RECEIVED
                self._log_event("TCP_SYN_RECEIVED", ["SYN"])

                return TCPPacket(
                    source_port=self.local_port,
                    destination_port=self.remote_port,
                    sequence_number=self.sequence_number,
                    acknowledgement_number=self.acknowledgement_number,
                    flags={"SYN", "ACK"}
                )
   
        elif self.state == TCPState.SYN_SENT:
            if "SYN" in packet.flags and "ACK" in packet.flags:

                if packet.acknowledgement_number == (self.sequence_number + 1):
                    self.acknowledgement_number = packet.sequence_number + 1
                    self.sequence_number += 1

                    self.state = TCPState.ESTABLISHED
                    self._log_event("TCP_ESTABLISHED", ["ACK"])

                    return TCPPacket(
                            source_port=self.local_port,
                            destination_port=self.remote_port,
                            sequence_number=self.sequence_number,
                            acknowledgement_number=self.acknowledgement_number,
                            flags={"ACK"}
                        )

        elif self.state == TCPState.SYN_RECEIVED:
            if not ("SYN" in packet.flags) and "ACK" in packet.flags:
            
                if packet.acknowledgement_number == (self.sequence_number + 1):

                    self.state = TCPState.ESTABLISHED
                    self._log_event("TCP_ESTABLISHED", ["ACK"])

        elif self.state == TCPState.FIN_WAIT1:

            #FIN was acknowledged 
            if "ACK" in packet.flags:
                
                if packet.acknowledgement_number != self.sequence_number:
                    return None

                self.state = TCPState.FIN_WAIT2
                self._log_event("TCP_FIN_ACK_RECEIVED", ["ACK"])

                #the peer is closing too, so we advance to closure
                if "FIN" in packet.flags:
        
                    self.acknowledgement_number = packet.sequence_number + 1
                    self.state = TCPState.TIME_WAIT
                    self.time_wait_remaining = TIME_WAIT_DURATION
                    self._log_event("TCP_TIME_WAIT", ["ACK"])
        
                    return TCPPacket(
                        source_port=self.local_port,
                        destination_port=self.remote_port,
                        sequence_number=self.sequence_number,
                        acknowledgement_number=self.acknowledgement_number,
                        flags={"ACK"}
                        )

                return None

            #peer sent FIN before acknowledging ours. we close the connection. since both parties have agreed to FIN
            if "FIN" in packet.flags: 
                
                self.acknowledgement_number = packet.sequence_number + 1
                self.state = TCPState.TIME_WAIT
                self.time_wait_remaining = TIME_WAIT_DURATION
                self._log_event("TCP_TIME_WAIT", ["ACK"])

                return TCPPacket(
                    source_port=self.local_port,
                    destination_port=self.remote_port,
                    sequence_number=self.sequence_number,
                    acknowledgement_number=self.acknowledgement_number,
                    flags={"ACK"}
                )
            return None

        elif self.state == TCPState.FIN_WAIT2:

            if "FIN" in packet.flags:

                
                self.acknowledgement_number = packet.sequence_number + 1
                self.state = TCPState.TIME_WAIT
                self.time_wait_remaining = TIME_WAIT_DURATION
                self._log_event("TCP_TIME_WAIT", ["ACK"])

                return TCPPacket(
                    source_port=self.local_port,
                    destination_port=self.remote_port,
                    sequence_number=self.sequence_number,
                    acknowledgement_number=self.acknowledgement_number,
                    flags = {"ACK"}
                )
            return None

        elif self.state == TCPState.TIME_WAIT:

            if "FIN" in packet.flags:
            
                self.acknowledgement_number = packet.sequence_number + 1
                self.time_wait_remaining = TIME_WAIT_DURATION
                self._log_event("TCP_TIME_WAIT_RETRANSMIT", ["ACK"])

                return TCPPacket(
                    source_port=self.local_port,
                    destination_port=self.remote_port,
                    sequence_number=self.sequence_number,
                    acknowledgement_number=self.acknowledgement_number,
                    flags={"ACK"}
                )

            return None

        elif self.state == TCPState.LAST_ACK:
            if "ACK" in packet.flags:

                if packet.acknowledgement_number != self.sequence_number:
                    return None

                self.state = TCPState.CLOSED
                self._log_event("TCP_CLOSED", ["ACK"])
                return None

            return None
        
        elif self.state == TCPState.ESTABLISHED:

            if "FIN" in packet.flags:

                self.acknowledgement_number = packet.sequence_number + 1
                self.state = TCPState.CLOSE_WAIT
                self._log_event("TCP_CLOSE_WAIT", ["ACK"])

                return TCPPacket(
                    source_port=self.local_port,
                    destination_port=self.remote_port,
                    sequence_number=self.sequence_number,
                    acknowledgement_number=self.acknowledgement_number,
                    flags={"ACK"}
                    )
      
        elif self.state == TCPState.CLOSE_WAIT:
            return None



        return None

    def send_data(self, data):
        if self.state != TCPState.ESTABLISHED:
            raise ValueError("TCP connection is not established")

        packet = TCPPacket(
            source_port=self.local_port,
            destination_port=self.remote_port,
            sequence_number=self.sequence_number,
            acknowledgement_number=self.acknowledgement_number,
            flags={"ACK"},
            payload=data
        )

        self.sequence_number += len(data)
        self._log_event("TCP_DATA_SENT", ["ACK"], {"data_length": len(data)})

        return packet

    def receive_data(self, packet: TCPPacket):

        if self.state != TCPState.ESTABLISHED:
            raise ValueError("TCP connection is not established")
    
        if "ACK" not in packet.flags:
            return None

        if self.acknowledgement_number != packet.sequence_number:
            return None

        payload_length = len(packet.payload) if packet.payload is not None else 0
    
        self.acknowledgement_number = (
            packet.sequence_number + payload_length
        )

        self._log_event("TCP_DATA_RECEIVED", ["ACK"], {"data_length": payload_length})
    
        return TCPPacket(
            source_port=self.local_port,
            destination_port=self.remote_port,
            sequence_number=self.sequence_number,
            acknowledgement_number=self.acknowledgement_number,
            flags={"ACK"}
        )

    def close(self):

        if self.state == TCPState.ESTABLISHED:
            packet = TCPPacket(
                source_port=self.local_port,
                destination_port=self.remote_port,
                sequence_number=self.sequence_number,
                acknowledgement_number=self.acknowledgement_number,
                flags={"FIN", "ACK"}
            )

            self.state = TCPState.FIN_WAIT1
            self.sequence_number += 1
            self._log_event("TCP_FIN_SENT", ["FIN", "ACK"])

            return packet

        if self.state == TCPState.CLOSE_WAIT:
            packet = TCPPacket(
                    source_port=self.local_port,
                    destination_port=self.remote_port,
                    sequence_number=self.sequence_number,
                    acknowledgement_number=self.acknowledgement_number,
                    flags={"FIN", "ACK"}
                )

            self.sequence_number += 1
            self.state = TCPState.LAST_ACK
            self._log_event("TCP_LAST_ACK", ["FIN", "ACK"])

            return packet

        raise ValueError(
            f"Cannot close connection from state {self.state.value}"
        )

    def listen(self):

        if self.state != TCPState.CLOSED:
            raise RuntimeError(
                f"Cannot listen from state {self.state.value}"
            )

        self.state = TCPState.LISTEN
        self._log_event("TCP_LISTEN", [])

        return None

    def tick(self, seconds):

        if self.state != TCPState.TIME_WAIT:
            return

        if seconds < 0:
            raise ValueError("seconds cannot be negative")

        self.time_wait_remaining -= seconds

        if self.time_wait_remaining <= 0:

            self.time_wait_remaining = None
            self.state = TCPState.CLOSED
            self._log_event("TCP_CLOSED_TIME_WAIT_EXPIRED", [])

    def reset(self):

        if self.state == TCPState.CLOSED:
            raise ValueError("Connection is already closed")

        self.state = TCPState.CLOSED
        self.time_wait_remaining = None
        self._log_event("TCP_RESET_SENT", ["RST"])

        return TCPPacket(
            source_port=self.local_port,
            destination_port=self.remote_port,
            sequence_number=self.sequence_number,
            acknowledgement_number=self.acknowledgement_number,
            flags={"RST"}
        )