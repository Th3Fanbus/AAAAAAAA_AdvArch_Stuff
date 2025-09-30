import selectors
import socket
import sys

#############################
#  CONFIGURATION CONSTANTS  #
#############################

# Host and port to try to connect to
HOST_PORT = ("localhost", 9999)

# Handle data from stdin
def userinput(stdin_fileno):
    data = stdin_fileno.readline().rstrip()
    if len(data) > 0:
        # Hack to clear the line using escape sequences
        # Not portable unless using colorama on Windows
        print("\033[A" + (" " * len(data)) + "\033[A")
        sock.sendall((data + "\n").encode("utf-8"))
    return False

# Handle data from server
def accept(sock):
    received = sock.recv(1024).decode("utf-8").rstrip()
    if len(received) > 0:
        print(received)
    return len(received) == 0

def selector_loop(sock, sel):
    while True:
        events = sel.select()
        # We don't use event masks
        for key, _ in events:
            callback = key.data
            exit_loop = callback(key.fileobj)
            if exit_loop:
                return

if __name__ == "__main__":
    # Create a socket (SOCK_STREAM means a TCP socket)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect(HOST_PORT)
        with selectors.DefaultSelector() as sel:
            sel.register(sock, selectors.EVENT_READ, accept)
            sel.register(sys.stdin, selectors.EVENT_READ, userinput)
            selector_loop(sock, sel)
    print("Byeeeee!")
