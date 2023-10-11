import socketserver
import threading

#############################
#  CONFIGURATION CONSTANTS  #
#############################

# Host and port to launch the server on
HOST_PORT = ("localhost", 9999)

# Number of players needed to start the game
PLAYERS_PER_GAME = 3

# TODO
PLAYER_JOIN_TIMEOUT_S = 60

# The server based on threads for each connection
class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    # DOC: ThreadingMixIn define un atributo daemon_threads, que indica
    #      si el servidor debe esperar o no la terminación del hilo
    daemon_threads = True
    allow_reuse_address = True

# Session of the game
class PlayerHandler(socketserver.StreamRequestHandler):
    def send(self, message):
        self.wfile.write(("%s\n"%message).encode('utf-8'))

    def handle(self):
        print("Connected: %s on %s"%(self.client_address,threading.current_thread().name))
        try:
            self.join_waiting_room()
            if threading.current_thread().name == "Thread-2 (process_request_thread)":
                pass
                # self.explode()
            self.await_others()
        except Exception as e:
            print(e)
            print("1 EXCEPTION CAUGHT? on %s"%threading.current_thread().name)
        finally:
            try:
                self.leave_waiting_room()
                # self.opponent.send('OTHER_PLAYER_LEFT')
            except Exception as e:
                # Hack for when the game ends, not happy about this
                print(e)
                print("2 EXCEPTION CAUGHT? on %s"%threading.current_thread().name)
                # pass
            print("Closed: client %s on %s"%(self.client_address,threading.current_thread().name))

    def join_waiting_room(self):
        WaitingRoom.join(self)
        self.send("Welcome!")
        self.send(self.waiting_room.format_num_players())

    def leave_waiting_room(self):
        print("Leaving: %s on %s"%(self.client_address,threading.current_thread().name))
        self.waiting_room.disconnect_player(self)

    def await_others(self):
        # TODO: exceptions
        self.send("AWAIT %d"%self.index)
        self.waiting_room.wait(self)
        # TODO: only print once on server, use barrier actions?
        # Also, clients need to be disconnected somehow?
        self.send("Game begins!")

class WaitingRoom():
    curr_waiting_room = None
    room_selection_lock = threading.Lock()

    @classmethod
    def join(cls, player):
        with cls.room_selection_lock:
            if cls.curr_waiting_room is None:
                cls.curr_waiting_room = WaitingRoom()

            # TOO MANY PLAYERS BEFORE CONNECTING?
            assert len(cls.curr_waiting_room.conn_players) < PLAYERS_PER_GAME

            cls.curr_waiting_room.connect_player(player)
            if cls.curr_waiting_room.num_players() >= PLAYERS_PER_GAME:
                print('GAME CAN BEGIN?')
                cls.curr_waiting_room = None

    def __init__(self):
        print('New Waiting Room')
        self.conn_players = []
        self.index = 0
        self.lock = threading.Lock()
        self.barrier = threading.Barrier(PLAYERS_PER_GAME)

    def connect_player(self, player):
        self.index += 1
        player.index = self.index
        player.waiting_room = self
        self.conn_players.append(player)
        return len(self.conn_players)

    def disconnect_player(self, player):
        self.conn_players.remove(player)

    def format_num_players(self):
        return "%d out of %d players connected"%(self.num_players(), PLAYERS_PER_GAME)

    def num_players(self):
        return len(self.conn_players)

    def wait(self, player):
        self.barrier.wait()

server = ThreadedTCPServer(HOST_PORT, PlayerHandler)
try:
    print('The waiting room server is running...')
    server.serve_forever()
except KeyboardInterrupt:
    pass
server.server_close()
print("Byeeeee!")
