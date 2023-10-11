import builtins
import selectors
import socket
import socketserver
import threading

#############################
#  CONFIGURATION CONSTANTS  #
#############################

# Host and port to launch the server on
# Empty host means "all available interfaces"
HOST_PORT = ("", 9999)

# Number of players needed to start the game
PLAYERS_PER_GAME = 3

# Server which spawns a new thread for each connection
class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    # DOC: ThreadingMixIn define un atributo daemon_threads, que indica
    #      si el servidor debe esperar o no la terminación del hilo
    daemon_threads = True
    allow_reuse_address = True

# Override print function to show the thread it's running on
def print(*args):
    thread_name = threading.current_thread().name.split()[0]
    builtins.print(("[%s] "%thread_name).ljust(20) + " ".join(map(str, args)))

class PlayerHandler(socketserver.StreamRequestHandler):
    def send(self, message):
        self.wfile.write(("%s\n"%message).encode('utf-8'))

    # Handle method
    def handle(self):
        print("Connected " + str(self.client_address))
        try:
            self.join_waiting_room()
            self.wait_room_full()
        finally:
            self.leave_waiting_room()
            print("Disconnected " + str(self.client_address))

    def join_waiting_room(self):
        WaitingRoom.join_room(self)
        self.send("<Server> Welcome!")

    def leave_waiting_room(self):
        print("Leaving: %s on %s"%(self.client_address, threading.current_thread().name))
        self.waiting_room.disconnect_player(self)

    @staticmethod
    def handle_conn(player, rfile):
        data = rfile.readline().decode('utf-8').rstrip()
        # Empty response means connection broke
        if not data:
            return True
        print("Data received: %s"%data)
        player.waiting_room.send_to_all("<PLAYER-{}> {}".format(player.index, data))
        return False

    @staticmethod
    def handle_state(player, sock):
        data = sock.recv(1024).decode('utf-8')
        # Empty response means connection broke
        if not data:
            raise NotImplementedError("handle_state missing exit condition")
            #return False
        for command in data.split():
            exit_loop = player.handle_command(command)
            if exit_loop:
                return True
        return False

    def handle_command(self, command):
        print("State received: %s"%command)
        match command:
            case "JOIN":
                self.send(self.waiting_room.format_num_players())
                return False
            case "QUIT":
                self.send(self.waiting_room.format_num_players())
                return False
            case "READY":
                self.send(self.waiting_room.format_num_players())
                self.send("<Server> Game begins!")
                return True
            case _:
                raise NotImplementedError("no idea what state this is: " + command)

    def server_loop(self, sel):
        while True:
            events = sel.select()
            # Ignore event masks
            for key, _ in events:
                callback = key.data
                exit_loop = callback(self, key.fileobj)
                if exit_loop:
                    return

    def wait_room_full(self):
        # TODO: exceptions?
        # self.send("AWAIT %d"%self.index)
        with selectors.DefaultSelector() as sel:
            try:
                sel.register(self.rfile, selectors.EVENT_READ, PlayerHandler.handle_conn)
                sel.register(self.rx_sock, selectors.EVENT_READ, PlayerHandler.handle_state)
                self.server_loop(sel)
            finally:
                sel.close()

    def await_others(self):
        pass

class WaitingRoom():
    curr_waiting_room = None
    room_selection_lock = threading.Lock()

    @classmethod
    def join_room(cls, player):
        with cls.room_selection_lock:
            if cls.curr_waiting_room is None:
                cls.curr_waiting_room = WaitingRoom()

            # TOO MANY PLAYERS BEFORE CONNECTING?
            assert len(cls.curr_waiting_room.conn_players) < PLAYERS_PER_GAME

            cls.curr_waiting_room.connect_player(player)
            if cls.curr_waiting_room.num_players() >= PLAYERS_PER_GAME:
                print("GAME CAN BEGIN?")
                cls.curr_waiting_room.signal_state_change("READY")
                cls.curr_waiting_room = None

    def __init__(self):
        print("New Waiting Room")
        self.conn_players = []
        self.index = 0
        self.lock = threading.Lock()

    def connect_player(self, player):
        self.index += 1
        player.index = self.index
        player.waiting_room = self
        player.rx_sock, player.tx_sock = socket.socketpair()
        self.conn_players.append(player)
        self.signal_state_change("JOIN")

    def disconnect_player(self, player):
        self.conn_players.remove(player)
        self.signal_state_change("QUIT")

    def send_to_all(self, message):
        for player in self.conn_players:
            player.send(message)

    def signal_state_change(self, message):
        for player in self.conn_players:
            player.tx_sock.send((message + "\n").encode())

    def format_num_players(self):
        return "<Server> %d out of %d players connected"%(self.num_players(), PLAYERS_PER_GAME)

    def num_players(self):
        return len(self.conn_players)

if __name__ == '__main__':
    server = ThreadedTCPServer(HOST_PORT, PlayerHandler)
    try:
        print("The waiting room server is running...")
        server.serve_forever()
    except KeyboardInterrupt:
        builtins.print("")
    finally:
        server.server_close()
    print("Byeeeee!")
