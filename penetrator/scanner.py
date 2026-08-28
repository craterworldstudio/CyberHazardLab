class PortScanner:

    def __init__(self, network):
        self.network = network

    def scan(self, source, target, start_port, end_port):
        results = []

        for port in range(start_port, end_port + 1):

            result = self.network.connect(
                source=source,
                destination=target,
                protocol="TCP",
                port=port
            )

            results.append({
                "port": port,
                "open": result == "ACCEPTED"
            })

        return results