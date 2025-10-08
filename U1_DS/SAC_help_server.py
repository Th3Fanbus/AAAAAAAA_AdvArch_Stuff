import builtins
import random
import selectors
import socket
import socketserver
import sys
import threading
import time
import warnings

#############################
#  CONFIGURATION CONSTANTS  #
#############################

# Host to launch the server on
# Empty host means "all available interfaces"
SERVER_HOST = ""

# Port base to use, note that an index is added to this
SERVER_PORT_BASE = 9990

# Override print function to show the thread it's running on
def print(*args):
    thread_name = threading.current_thread().name.split()[0]
    builtins.print(("[%s] "%thread_name).ljust(20) + " ".join(map(str, args)))

class Helper:
    def __init__(self, addr, client_sock):
        self.addr = addr
        self.client_sock = client_sock

    def __enter__(self):
        print("Connected " + self.addr)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client_sock.close()
        print("Disconnected " + self.addr)

    def decide_response(self):
        value = random.randint(1, 10)
        if value == 10:
            print("Responding ---> [timed out: analysis paralysis]")
            return None
        elif value <= 4:
            print("Responding ---> ok!")
            return "ok!"
        else:
            print("Responding ---> no!")
            return "no!"

    def handle_sock(self, sock):
        data = sock.recv(1024).decode("utf-8").rstrip()
        # Empty response means connection broke
        if not data:
            return True
        print("Data received: %s"%data)
        if data == "help!":
            time.sleep(random.randint(1, 2))
            response = self.decide_response()
            if response is not None:
                sock.sendall(response.encode("utf-8"))
        return False

    def selector_loop(self, sel):
        while True:
            events = sel.select()
            # Ignore event masks
            for key, _ in events:
                callback = key.data
                exit_loop = callback(key.fileobj)
                if exit_loop:
                    return

    def serve_requests_forever(self):
        with selectors.DefaultSelector() as sel:
            sel.register(self.client_sock, selectors.EVENT_READ, self.handle_sock)
            self.selector_loop(sel)

class HelperHandler(socketserver.BaseRequestHandler):
    # When the server receives an incoming connection,
    # this method gets executed in a dedicated thread.
    def handle(self):
        # We use a context manager to easily release resources on exit
        with Helper(str(self.client_address), self.request) as helper:
            helper.serve_requests_forever()

# Server which spawns a new thread for each connection
class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <ID>")
    else:
        port = SERVER_PORT_BASE + int(sys.argv[1])
        print(f"Starting server on '{SERVER_HOST}:{port}'...")
        with ThreadedTCPServer((SERVER_HOST, port), HelperHandler) as server:
            print("Server ready!")
            server.serve_forever()
        print("Byeeeee!")
