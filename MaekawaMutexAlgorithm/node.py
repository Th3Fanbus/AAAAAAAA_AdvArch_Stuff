from threading import Event, Thread, Timer, Condition
from datetime import datetime, timedelta
import random, time
from nodeServer import NodeServer
from nodeSend import NodeSend
from message import Message
import config

STATE_RELEASED = 0
STATE_WANTED   = 1
STATE_HELD     = 2

class Node(Thread):
    _FINISHED_NODES = 0
    _HAVE_ALL_FINISHED = Condition()

    def __init__(self,id):
        Thread.__init__(self)
        self.id = id
        self.port = config.port + id
        self.daemon = True
        self.lamport_ts = 0

        # Init variables
        self.proc_state = STATE_RELEASED
        self.voted = False
        self.deadlocked = False
        self.num_replies = 0
        self.req_queue = []
        self.grants_received = []

        self.server = NodeServer(self)
        self.server.start()

        #TODO OPTIONAL This is a simple way to define the collegues, but it is not the best way to do it.
        # You can implement a more complex way to define the collegues, but for now this is enough.
        if id % 2 == 0:
            self.collegues = list(range(0,config.numNodes,2))
        else:
            self.collegues = list(range(1,config.numNodes,2))

        self.client = NodeSend(self)

    def do_connections(self):
        self.client.build_connection()

    def process_message(self, msg):
        # Handle received messages:
        # - greetings
        #   do nothing
        # - request
        #   On receipt of a request from pi at pj:
        #   if (state = HELD or voted = TRUE) then
        #     queue request from pi without replying
        #   else
        #     send reply to pi
        #     voted := TRUE
        #   end if
        # - grant (reply)
        #   TODO: how to handle
        # - release
        #   On receipt of a release from pi at pj
        #   if (queue of requests is non-empty) then
        #     remove head of queue – from pk , say
        #     send reply to pk
        #     voted := TRUE
        #   else
        #     voted := FALSE
        #   end if
        # These are for the no-deadlock version
        # - yield
        # - inquire
        # - failed
        # {'msg_type': 'request', 'src': 1, 'dest': 1, 'ts': 1, 'data': '1'}
        print(f"Node_{self.id} receive msg: {msg}")
        match msg:
            case {"msg_type": "greetings"}:
                pass
            case {"msg_type": "request", "src": msg_src}:
                if self.proc_state == STATE_HELD or self.voted:
                    #print(f"[node {self.id}] storing request from {msg_src}")
                    self.req_queue.append(msg_src)
                else:
                    #print(f"[node {self.id}] granting request from {msg_src}")
                    message = Message(msg_type="grant",
                                      src=self.id,
                                      dest=msg_src,
                                      data="%i"%(self.id))
                    self.client.send_message(message, msg_src)
                    self.voted = True
            case {"msg_type": "grant", "src": msg_src}:
                #print(f"[node {self.id}] granted from {msg_src}")
                self.grants_received.append(msg_src)
            case {"msg_type": "release", "src": msg_src}:
                #print(f"[node {self.id}] got release from {msg_src}")
                if len(self.req_queue) > 0:
                    #self.req_queue.sort()
                    grant_dst = self.req_queue.pop(0)
                    message = Message(msg_type="grant",
                                      src=self.id,
                                      dest=grant_dst,
                                      data="%i"%(self.id))
                    self.client.send_message(message, grant_dst)
                    voted = True
                else:
                    voted = False

    def pre_protocol(self):
        def try_acquiring():
            self.grants_received = []
            self.proc_state = STATE_WANTED
            print(f"[node {self.id}] I want the mutex")
            message = Message(msg_type="request",
                              src=self.id,
                              data="%i"%(self.id))
            self.client.multicast(message, self.collegues)
            while len(self.grants_received) < len(self.collegues):
                #print(f"[node {self.id}] {self.collegues}, {self.grants_received}")
                time.sleep(0)
                if self.deadlocked:
                    self.deadlocked = False
                    self.req_queue = []
                    return False
            return True

        while not try_acquiring():
            pass
        self.proc_state = STATE_HELD
        print(f"[node {self.id}] {self.collegues}, {self.grants_received}, {self.req_queue}")
        print(f"[node {self.id}] I HAVE DA MUTEX")

    def post_protocol(self):
        print(f"[node {self.id}] Releasing mutex")
        self.proc_state = STATE_RELEASED
        message = Message(msg_type="release",
                          src=self.id,
                          data="%i"%(self.id))
        self.client.multicast(message, self.collegues)

    def run(self):
        NUM_WAKEUPS = 20

        print("Run Node%i with the follows %s"%(self.id,self.collegues))
        self.client.start()

        #TODO MANDATORY Change this loop to simulate the Maekawa algorithm to
        # - Request the lock
        # - Wait for the lock
        # - Release the lock
        # - Repeat until some condition is met (e.g. timeout, wakeupcounter == 3)

        self.wakeupcounter = 0
        while self.wakeupcounter <= NUM_WAKEUPS: # Termination criteria
            # Nodes with different starting times
            time_offset = random.randint(0, 1)
            time.sleep(time_offset)

            self.pre_protocol()

            # A dummy message
            print(f"This is Node_{self.id} at TS:{self.lamport_ts} sending a message to my collegues")
            #self.lamport_ts += 1 # Increment the timestamp
            message = Message(msg_type="greetings",
                              src=self.id,
                              data=f"Hola, this is Node_{self.id} _ counter:{self.wakeupcounter}")

            self.client.multicast(message, self.collegues)

            self.post_protocol()

            # Control iteration
            self.wakeupcounter += 1

        # Wait for all nodes to finish
        print(f"Node_{self.id} is waiting for all nodes to finish")
        self._finished()

        print(f"Node_{self.id} DONE!")

    #TODO OPTIONAL you can change the way to stop
    def _finished(self):
        with Node._HAVE_ALL_FINISHED:
            Node._FINISHED_NODES += 1
            if Node._FINISHED_NODES == config.numNodes:
                Node._HAVE_ALL_FINISHED.notify_all()

            while Node._FINISHED_NODES < config.numNodes:
                Node._HAVE_ALL_FINISHED.wait()
