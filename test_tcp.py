from backend.network.tcp import TCPConnection

client = TCPConnection(
    local_ip="10.0.2.100",
    local_port=49152,
    remote_ip="10.0.0.100",
    remote_port=80
)
#print("Client", client.state)
syn = client.connect()
#print("Client", client.state)
server = TCPConnection(
    local_ip="10.0.0.100",
    local_port=80,
    remote_ip="10.0.2.100",
    remote_port=49152
)
#print("Server", server.state)
syn_ack = server.receive(syn)
#print("Server", server.state)
ack = client.receive(syn_ack)
#print("Client", client.state)
server.receive(ack)
#print("Server", server.state)

#print(syn)
#print(syn_ack)
#print(ack)


data = client.send_data("Hello")
print(data)
data_ack = server.receive_data(data)
print(data_ack)