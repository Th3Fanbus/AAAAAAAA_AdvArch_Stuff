import socket

#############################
#  CONFIGURATION CONSTANTS  #
#############################

# Host and port to try to connect to
HOST_PORT = ("localhost", 9999)

# Create a socket (SOCK_STREAM means a TCP socket)
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    # Connect to server and send data
    sock.connect(HOST_PORT)
    while True:
        data = input("Enter input: ")
        sock.sendall(bytes(data + "\n", "utf-8"))
        # Receive data from the server
        received = str(sock.recv(1024), "utf-8")
        if len(received) == 0:
            break
        print(received)

print("Byeeeee!")
