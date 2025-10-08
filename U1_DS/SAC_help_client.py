import contextlib
import random
import selectors
import socket
import sys
import time

#############################
#  CONFIGURATION CONSTANTS  #
#############################

# Host to try to connect to
SERVER_HOST = "localhost"

# Port base to use, note that an index is added to this
SERVER_PORT_BASE = 9990

# The timeout for a response to arrive when asking for help
RESP_TIMEOUT_SECONDS = 3

#############################
#  CONFIGURATION FUNCTIONS  #
#############################

# The lowest number of accepted help requests
def min_accepted_help_req_num(num_helpers):
    return num_helpers // 2 + 1

# Check the case of 3 helpers (what the instructions say)
assert min_accepted_help_req_num(3) == 2

class Client:
    def __init__(self, hosts_ports):
        # Create a socket (SOCK_STREAM means a TCP socket)
        self.sockets = {socket.socket(socket.AF_INET, socket.SOCK_STREAM): host_port for host_port in hosts_ports}

    def __enter__(self):
        for sock, host_port in self.sockets.items():
            sock.__enter__()
            print(f"Connecting to '{host_port[0]}:{host_port[1]}'...")
            sock.connect(host_port)
        print("Connected!")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for sock, host_port in self.sockets.items():
            sock.close()
            sock.__exit__(exc_type, exc_val, exc_tb)

    # Handle data from server
    def handle_response(self, sock):
        return sock.recv(1024).decode("utf-8").rstrip()

    def get_responses(self, sel):
        init_time = time.monotonic()
        responses = {}
        got_help = False
        while True:
            events = sel.select(RESP_TIMEOUT_SECONDS)
            # We don't use event masks
            for key, _ in events:
                callback = key.data
                sock = key.fileobj
                responses.update({sock: callback(sock)})
            # Check if we have enough ok responses
            num_ok_responses = 0
            for _, data in responses.items():
                if data == "ok!":
                    num_ok_responses += 1
            if num_ok_responses >= min_accepted_help_req_num(len(self.sockets)):
                got_help = True
                break
            # All responses acquired, no need to wait any further
            if len(responses) == len(self.sockets):
                break
            curr_time = time.monotonic()
            if curr_time - init_time > RESP_TIMEOUT_SECONDS:
                break
        print(f"Got {len(responses)} responses:")
        for sock, data in responses.items():
            print(f"[{sock}]:\t{data}")
        return got_help

    def main_loop(self):
        while True:
            with selectors.DefaultSelector() as sel:
                for sock, _ in self.sockets.items():
                    sock.sendall("help!".encode("utf-8"))
                    sel.register(sock, selectors.EVENT_READ, self.handle_response)
                print()
                print("Asking for help!")
                got_help = self.get_responses(sel)
                # Log result of getting responses
                print()
                if got_help:
                    print("Got enough help!!!")
                    return
                print("Did not receive enough help...")
                print()
                print("Zzzzz...")
                time.sleep(random.randint(1, 1)) # Range changed for convenience of testing
                print()
                print()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"usage: {sys.argv[0]} <ID>")
    else:
        with Client([(SERVER_HOST, SERVER_PORT_BASE + int(port)) for port in sys.argv[1:]]) as client:
            client.main_loop()
        print("Byeeeee!")
