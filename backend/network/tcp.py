from enum import Enum
from .packet import TCPPacket

class TCPState(Enum):
    CLOSED = "CLOSED"
    LISTEN = "LISTEN"
    SYN_SENT = "SYN_SENT"
    SYN_RECEIVED = "SYN_RECEIVED"
    ESTABLISHED = "ESTABLISHED"
    FIN_WAIT = "FIN_WAIT"
    CLOSE_WAIT = "CLOSE_WAIT"

class TCPConnection:

    def __init__(
        self,
        local_ip: str, local_port: int,
        remote_ip: str, remote_port: int
    ):
        self.local_ip = local_ip
        self.local_port = local_port

        self.remote_ip = remote_ip
        self.remote_port = remote_port

        self.state = TCPState.CLOSED

        self.sequence_number = 0
        self.acknowledgement_number = 0


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

        return packet

    def receive(self, packet: TCPPacket):

        if self.state == TCPState.CLOSED:

            if "SYN" in packet.flags and not ("ACK" in packet.flags):

                self.acknowledgement_number = packet.sequence_number + 1
                self.sequence_number = 5000

                self.state = TCPState.SYN_RECEIVED

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

        if self.state == TCPState.ESTABLISHED:

            if "FIN" in packet.flags:

                self.acknowledgement_number = packet.sequence_number + 1
                self.state = TCPState.CLOSE_WAIT

            return TCPPacket(
                source_port=self.local_port,
                destination_port=self.remote_port,
                sequence_number=self.sequence_number,
                acknowledgement_number=self.acknowledgement_number,
                flags={"ACK"}
                )

        if self.state == TCPState.FIN_WAIT:

            if "FIN" in packet.flags:

                self.acknowledgement_number = packet.sequence_number + 1
                self.state = TCPState.CLOSED

            return TCPPacket(
                    source_port=self.local_port,
                    destination_port=self.remote_port,
                    sequence_number=self.sequence_number,
                    acknowledgement_number=self.acknowledgement_number,
                    flags={"ACK"}
                    )

        if self.state == TCPState.CLOSE_WAIT:

            if "ACK" in packet.flags:

                self.state = TCPState.CLOSED
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
    
        return TCPPacket(
            source_port=self.local_port,
            destination_port=self.remote_port,
            sequence_number=self.sequence_number,
            acknowledgement_number=self.acknowledgement_number,
            flags={"ACK"}
        )

    def close(self):

        if self.state not in {
                TCPState.ESTABLISHED, TCPState.CLOSE_WAIT }:
            raise ValueError("TCP connection is not established")

        self.state = TCPState.FIN_WAIT
        self.sequence_number += 1

        return TCPPacket(
            source_port=self.local_port,
            destination_port=self.remote_port,
            sequence_number=self.sequence_number,
            acknowledgement_number=self.acknowledgement_number,
            flags={"FIN", "ACK"}
        )
