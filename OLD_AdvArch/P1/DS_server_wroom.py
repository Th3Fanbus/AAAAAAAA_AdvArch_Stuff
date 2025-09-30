import builtins
import selectors
import socket
import socketserver
import threading
import time
import warnings

#############################
#  CONFIGURATION CONSTANTS  #
#############################

# Host and port to launch the server on
# Empty host means "all available interfaces"
HOST_PORT = ("", 9999)

# Number of players needed to start the game
PLAYERS_PER_GAME = 3

# The number of seconds to start counting down from
COUNTDOWN_SECONDS = 3

# Override print function to show the thread it's running on
def print(*args):
    thread_name = threading.current_thread().name.split()[0]
    builtins.print(("[%s] "%thread_name).ljust(20) + " ".join(map(str, args)))

class Player:
    def __init__(self, addr, client_sock):
        self.addr = addr
        self.client_sock = client_sock

    def __enter__(self):
        self.grp_rx_sock, self.grp_tx_sock = socket.socketpair()
        print("Connected " + self.addr)
        WaitingRoom.join_room(self)
        self.send("<Server> Welcome!")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.waiting_room.disconnect_player(self)
        self.grp_rx_sock.close()
        self.grp_tx_sock.close()
        self.client_sock.close()
        print("Disconnected " + self.addr)

    def send(self, message):
        self.client_sock.sendall((message + "\n").encode("utf-8"))

    def handle_chat(self, sock):
        data = sock.recv(1024).decode("utf-8").rstrip()
        # Empty response means connection broke
        if not data:
            return True
        print("Data received: %s"%data)
        self.waiting_room.send_to_all("<PLAYER-{}> {}".format(self.index, data))
        return False

    def handle_room(self, sock):
        data = sock.recv(1024).decode("utf-8").rstrip()
        # Empty response means connection broke
        if not data:
            # Should never happen, this socket comes from socketpair()
            # and we only close them after exiting the selector loop.
            warnings.warn("Local socket closed unexpectedly", RuntimeWarning)
            return True
        for event in data.split():
            exit_loop = self.handle_event(event)
            if exit_loop:
                return True
        return False

    def handle_event(self, command):
        print("State received: %s"%command)
        match command:
            case "JOIN":
                self.send(self.waiting_room.format_num_players())
                return False
            case "QUIT":
                self.send(self.waiting_room.format_num_players())
                return False
            case "READY":
                return True
            case _:
                raise NotImplementedError("no idea what state this is: " + command)

    def selector_loop(self, sel):
        while True:
            events = sel.select()
            # Ignore event masks
            for key, _ in events:
                callback = key.data
                exit_loop = callback(key.fileobj)
                if exit_loop:
                    return

    def wait_room_full(self):
        with selectors.DefaultSelector() as sel:
            sel.register(self.client_sock, selectors.EVENT_READ, self.handle_chat)
            sel.register(self.grp_rx_sock, selectors.EVENT_READ, self.handle_room)
            self.selector_loop(sel)

    def countdown_to_game(self):
        # WARNING: countdown does not handle client disconnects
        # Workaround: just remove or disable the damn countdown
        for n in range(COUNTDOWN_SECONDS, 0, -1):
            self.send("<Server> Game starting in %d"%n)
            time.sleep(1)
        self.send("<Server> Game begins!")

class WaitingRoom():
    curr_waiting_room = None
    room_selection_lock = threading.Lock()

    @classmethod
    def join_room(cls, player):
        room_full = False
        with cls.room_selection_lock:
            if cls.curr_waiting_room is None:
                cls.curr_waiting_room = WaitingRoom()
            # TOO MANY PLAYERS BEFORE CONNECTING?
            assert len(cls.curr_waiting_room.conn_players) < PLAYERS_PER_GAME
            cls.curr_waiting_room.connect_player(player)
            # TOO MANY PLAYERS AFTER CONNECTING?
            assert len(cls.curr_waiting_room.conn_players) <= PLAYERS_PER_GAME
            if cls.curr_waiting_room.num_players() == PLAYERS_PER_GAME:
                cls.curr_waiting_room = None
                room_full = True
        # Do not send stuff through sockets while holding a lock
        player.waiting_room.signal_state_change("JOIN")
        if room_full:
            print("Game can begin!")
            player.waiting_room.signal_state_change("READY")

    def __init__(self):
        print("New Waiting Room")
        self.conn_players = []
        self.index = 0
        self.lock = threading.Lock()

    def connect_player(self, player):
        self.index += 1
        player.index = self.index
        player.waiting_room = self
        self.conn_players.append(player)

    def disconnect_player(self, player):
        self.conn_players.remove(player)
        self.signal_state_change("QUIT")

    def send_to_all(self, message):
        for player in self.conn_players:
            player.send(message)

    def signal_state_change(self, message):
        for player in self.conn_players:
            player.grp_tx_sock.sendall((message + "\n").encode("utf-8"))

    def format_num_players(self):
        return "<Server> %d out of %d players connected"%(self.num_players(), PLAYERS_PER_GAME)

    def num_players(self):
        return len(self.conn_players)

class PlayerHandler(socketserver.BaseRequestHandler):
    # When the server receives an incoming connection,
    # this method gets executed in a dedicated thread.
    def handle(self):
        # We use a context manager to easily release resources on exit
        with Player(str(self.client_address), self.request) as player:
            player.wait_room_full()
            player.countdown_to_game()

# Server which spawns a new thread for each connection
class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    # DOC: ThreadingMixIn define un atributo daemon_threads, que indica
    #      si el servidor debe esperar o no la terminación del hilo
    daemon_threads = True
    allow_reuse_address = True

if __name__ == "__main__":
    with ThreadedTCPServer(HOST_PORT, PlayerHandler) as server:
        print("The waiting room server is running...")
        server.serve_forever()
    print("Byeeeee!")
