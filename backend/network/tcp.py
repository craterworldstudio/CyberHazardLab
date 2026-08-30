from enum import Enum
from .packet import TCPPacket

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
        remote_ip: str, remote_port: int
    ):
        self.local_ip = local_ip
        self.local_port = local_port

        self.remote_ip = remote_ip
        self.remote_port = remote_port

        self.state = TCPState.CLOSED

        self.sequence_number = 0
        self.acknowledgement_number = 0

        self.time_wait_remaining = None


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
        if "RST" in packet.flags:
            self.state = TCPState.CLOSED
            return None

        elif self.state == TCPState.LISTEN:

            if "SYN" in packet.flags and "ACK" not in packet.flags:

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

        elif self.state == TCPState.FIN_WAIT1:

            #FIN was acknowledged 
            if "ACK" in packet.flags:

                self.state = TCPState.FIN_WAIT2

                #the peer is closing too, so we advance to closure
                if "FIN" in packet.flags:
        
                    self.acknowledgement_number = packet.sequence_number + 1
                    self.state = TCPState.TIME_WAIT
                    self.time_wait_remaining = 60
        
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
                self.time_wait_remaining = 60

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
                self.time_wait_remaining = 60

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
                self.time_wait_remaining = 60

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
                self.state = TCPState.CLOSED
        
        elif self.state == TCPState.ESTABLISHED:

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

    def tick(self, seconds):

        if self.state != TCPState.TIME_WAIT:
            return

        self.time_wait_remaining -= seconds

        if self.time_wait_remaining <= 0:

            self.time_wait_remaining = None
            self.state = TCPState.CLOSED

    def reset(self):

        if self.state == TCPState.CLOSED:
            raise ValueError("Connection is already closed")

        self.state = TCPState.CLOSED

        return TCPPacket(
            source_port=self.local_port,
            destination_port=self.remote_port,
            sequence_number=self.sequence_number,
            acknowledgement_number=self.acknowledgement_number,
            flags={"RST"}
        )