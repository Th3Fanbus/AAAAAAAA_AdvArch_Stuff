import select
from threading import Thread
import utils
from message import Message
import json
import traceback

STATE_RELEASED = 0
STATE_WANTED   = 1
STATE_HELD     = 2

def split_json_blocks(multimsg):
    delim = '''{"msg_type"'''
    return [delim + e for e in multimsg.split(delim) if e]

class NodeServer(Thread):
    def __init__(self, node):
        Thread.__init__(self)
        self.node = node
        self.daemon = True

    def run(self):
        self.update()

    def update(self):
        self.connection_list = []
        self.server_socket = utils.create_server_socket(self.node.port)
        self.connection_list.append(self.server_socket)

        while self.node.daemon:
            (read_sockets, write_sockets, error_sockets) = select.select(
                self.connection_list, [], [], 5)
            if not (read_sockets or write_sockets or error_sockets):
                print('NS%i - Timed out'%self.node.id) #force to assert the while condition
                print(f"[node {self.node.id}] {self.node.collegues}, {self.node.grants_received}, {self.node.req_queue}")
                self.node.deadlocked = True
            else:
                for read_socket in read_sockets:
                    if read_socket == self.server_socket:
                        (conn, addr) = read_socket.accept()
                        self.connection_list.append(conn)
                    else:
                        try:
                            msg_stream = read_socket.recvfrom(4096)
                            # Sometimes you can get multiple JSON messages together
                            for multimsg in msg_stream:
                                if multimsg is None:
                                    continue
                                #print(multimsg)
                                for msg in split_json_blocks(str(multimsg, "utf-8")):
                                    #print(f"MSG[len={len(msg)}, msg={msg}]")
                                    try:
                                        #print(msg)
                                        ms = json.loads(msg)
                                        self.process_message(ms)
                                    except Exception:
                                        print(traceback.format_exc())
                        except:
                            read_socket.close()
                            self.connection_list.remove(read_socket)
                            continue

        self.server_socket.close()

    def process_message(self, msg):
        #TODO MANDATORY manage the messages according to the Maekawa algorithm (TIP: HERE OR IN ANOTHER FILE...)
        self.node.process_message(msg)

