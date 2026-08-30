
from backend.network.tcp import TCPConnection, TCPState


# ============================================================
# CREATE CONNECTIONS
# ============================================================

client = TCPConnection(
    local_ip="10.0.2.100",
    local_port=49152,
    remote_ip="10.0.0.100",
    remote_port=80
)

server = TCPConnection(
    local_ip="10.0.0.100",
    local_port=80,
    remote_ip="10.0.2.100",
    remote_port=49152
)


# ============================================================
# TCP THREE-WAY HANDSHAKE
# ============================================================

print("=== HANDSHAKE ===")

syn = client.connect()

print("Client:", client.state)

syn_ack = server.receive(syn)

print("Server:", server.state)

ack = client.receive(syn_ack)

print("Client:", client.state)

server.receive(ack)

print("Server:", server.state)


# ============================================================
# DATA
# ============================================================

print("\n=== DATA ===")

data = client.send_data("Hello")

print("Client sent:")
print(data)

data_ack = server.receive_data(data)

print("Server received data")
print("Server ACK:")
print(data_ack)

print("Client sequence:", client.sequence_number)
print("Server acknowledgement:", server.acknowledgement_number)


# ============================================================
# CLIENT ACTIVE CLOSE
# ============================================================

print("\n=== CLIENT CLOSE ===")

fin = client.close()

print("Client sent FIN:")
print(fin)

print("Client:", client.state)


# ============================================================
# SERVER RECEIVES FIN
# ============================================================

print("\n=== SERVER RECEIVES FIN ===")

server_response = server.receive(fin)

print("Server response:")
print(server_response)

print("Server:", server.state)


# ============================================================
# CLIENT RECEIVES FIN ACK
# ============================================================

print("\n=== CLIENT RECEIVES FIN ACK ===")

client_response = client.receive(server_response)

print("Client response:")
print(client_response)

print("Client:", client.state)


# ============================================================
# SERVER SENDS ITS FIN
# ============================================================

print("\n=== SERVER CLOSE ===")

server_fin = server.close()

print("Server sent FIN:")
print(server_fin)

print("Server:", server.state)


# ============================================================
# CLIENT RECEIVES SERVER FIN
# ============================================================

print("\n=== CLIENT RECEIVES SERVER FIN ===")

client_final_ack = client.receive(server_fin)

print("Client final ACK:")
print(client_final_ack)

print("Client:", client.state)


# ============================================================
# SERVER RECEIVES FINAL ACK
# ============================================================

print("\n=== SERVER RECEIVES FINAL ACK ===")

server.receive(client_final_ack)

print("Server:", server.state)


# ============================================================
# FINAL STATE
# ============================================================

print("\n=== FINAL STATES ===")

print("Client:", client.state)
print("Server:", server.state)
