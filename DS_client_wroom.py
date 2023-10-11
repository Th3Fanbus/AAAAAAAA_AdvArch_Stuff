import selectors
import socket
import sys

#############################
#  CONFIGURATION CONSTANTS  #
#############################

# Host and port to try to connect to
HOST_PORT = ("localhost", 9999)

def userinput(stdin_fileno):
    data = stdin_fileno.readline().rstrip()
    if len(data) > 0:
        print("\033[A" + (" " * len(data)) + "\033[A")
        sock.sendall(bytes(data + "\n", "utf-8"))
    return False

def accept(sock):
    # Receive data from the server
    received = sock.recv(1024).decode("utf-8").rstrip()
    if len(received) > 0:
        print(received)
    return len(received) == 0

def client_loop(sock, sel):
    while True:
        events = sel.select()
        # Ignore event masks
        for key, _ in events:
            callback = key.data
            exit_loop = callback(key.fileobj)
            if exit_loop:
                return

if __name__ == '__main__':
    # Create a socket (SOCK_STREAM means a TCP socket)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        # Connect to server and send data
        sock.connect(HOST_PORT)
        #sock.setblocking(False)
        with selectors.DefaultSelector() as sel:
            try:
                sel.register(sock, selectors.EVENT_READ, accept)
                sel.register(sys.stdin, selectors.EVENT_READ, userinput)
                client_loop(sock, sel)
            finally:
                sel.close()
    print("Byeeeee!")
