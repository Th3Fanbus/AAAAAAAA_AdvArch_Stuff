import asyncio
import curses
import datetime
import itertools
import json
import os
import signal
import threading
import time
import logging
import secrets

from gmqtt import Client as MQTTClient
from gmqtt.mqtt import constants as GMQTTConstants

#############################
#  CONFIGURATION CONSTANTS  #
#############################

# Whether to use uvloop instead of asyncio's default event loop
USE_UVLOOP = True

# Enable debug prints about MQTT messages
DEBUG_MQTT = not False

# MQTT version to use, need v3.1.1 for RabbitMQ
MQTT_VERSION = GMQTTConstants.MQTTv311

# Host to try to connect to
BROKER_HOST = "localhost"

# MQTT credentials
MQTT_USER_PASS = ("guest", "guest")

# Topic names, class only used to avoid name captures
class Topics:
    # Topic to use for matchmaking
    MATCHMAKING = "matchmaking"
    # Topic to use for game flow
    GAME_FLOW = "game_flow"

# Message type names for matchmaking topic
class Matchmaking:
    # Hello message, with proposed idx (position in the queue)
    HI_PROPOSE = "hi_propose"
    # Response to proposed idx when our own idx is greater (no queue skipping)
    RAISE_IDX = "raise_idx"
    # Request to initiate a game
    START_REQ = "start_req"
    # Accept initiating a game
    START_ACK = "start_ack"

class GameFlow:
    PLAY_MOVE = "play_move"

#############################
#  CONFIGURATION FUNCTIONS  #
#############################

# Get a client ID, must be different between invocations of the program
def cf_get_client_id():
    return secrets.token_hex(4)

if USE_UVLOOP:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

g_stop_evt = asyncio.Event()

def debug_print(*args):
    #print(*args)
    pass

class TicTacToeClient(MQTTClient):
    @staticmethod
    def s_on_connect(client, flags, rc, properties):
        if DEBUG_MQTT:
            debug_print(f"MQTT.CONNECTED {client._client_id} FLAGS: {flags} RC: {rc} PROPERTIES: {properties}")
        client.enqueue_coro(client.do_on_connect(flags, rc, properties))

    @staticmethod
    def s_on_message(client, topic, payload, qos, properties):
        if DEBUG_MQTT:
            debug_print(f"MQTT.Recv {client._client_id} TOPIC: {topic} PAYLOAD: '{payload.decode()}' QOS: {qos} PROPERTIES: {properties}")
        client.enqueue_coro(client.do_on_message(topic, payload, qos, properties))

    @staticmethod
    def s_on_disconnect(client, packet, exc=None):
        if DEBUG_MQTT:
            debug_print(f"MQTT.DISCONNECTED {client._client_id}")
        client.enqueue_coro(client.do_on_disconnect(packet, exc))

    @staticmethod
    def s_on_subscribe(client, mid, qos, properties):
        if DEBUG_MQTT:
            debug_print(f"MQTT.SUSCRIBED {client._client_id} MID: {mid} QOS: {qos} PROPERTIES: {properties}")
        client.enqueue_coro(client.do_on_subscribe(mid, qos, properties))

    @staticmethod
    def s_on_unsubscribe(client, mid, qos):
        if DEBUG_MQTT:
            debug_print(f"MQTT.UNSUSCRIBED {client._client_id} MID: {mid} QOS: {qos}")
        client.enqueue_coro(client.do_on_unsubscribe(mid, qos))

    def __init__(self):
        super().__init__(cf_get_client_id())
        self.on_connect = TicTacToeClient.s_on_connect
        self.on_message = TicTacToeClient.s_on_message
        self.on_disconnect = TicTacToeClient.s_on_disconnect
        self.on_subscribe = TicTacToeClient.s_on_subscribe
        self.on_unsubscribe = TicTacToeClient.s_on_unsubscribe
        self.set_auth_credentials(*MQTT_USER_PASS)

        self.queue_idx = 0
        self.subscribe_queue = asyncio.Queue()
        self.unsubscribe_queue = asyncio.Queue()
        self.publish_dict = {}
        self.running_tasks = set()
        self.task_lock = threading.Lock()
        self.found_opponent = asyncio.Event()
        self.game_begins = asyncio.Event()
        self.my_turn = False
        self.opponent_id = 0
        self.board_cells = []

    def enqueue_coro(self, coro):
        asyncio.get_event_loop().call_soon_threadsafe(self.enqueue_task, asyncio.create_task(coro))

    def enqueue_task(self, task):
        with self.task_lock:
            self.running_tasks.add(task)
        task.add_done_callback(self.cleanup_task)

    def cleanup_task(self, task):
        assert task.done()
        with self.task_lock:
            self.running_tasks.remove(task)

    # Event handlers
    async def do_on_connect(self, flags, rc, properties):
        pass

    async def do_on_message(self, fulltopic, payload, qos, properties):
        match fulltopic.split("/"):
            case [topic, self._client_id]:
                self.publish_dict[topic].set()
                pass
            case [Topics.MATCHMAKING, sender_id]:
                match json.loads(payload):
                    case {"type": Matchmaking.HI_PROPOSE, "idx": proposed_idx}:
                        # Someone new joined and is probing for the largest index
                        if proposed_idx <= self.queue_idx:
                            # If their proposed index is lower than ours, complain about it
                            await self.do_publish(Topics.MATCHMAKING, {
                                "type": Matchmaking.RAISE_IDX,
                                "idx": self.queue_idx + 1,
                                "dst": sender_id
                            })
                        else:
                            # If their proposed index is OK, try to initiate a game
                            await self.do_publish(Topics.MATCHMAKING, {
                                "type": Matchmaking.START_REQ,
                                "dst": sender_id
                            })
                    case {"type": Matchmaking.RAISE_IDX, "idx": new_idx, "dst": target_id} if target_id == self._client_id:
                        # Someone said we have to raise our index
                        if new_idx > self.queue_idx:
                            # If greater than our current index, update and publish updated ID
                            self.queue_idx = new_idx
                            await self.do_publish(Topics.MATCHMAKING, {
                                "type": Matchmaking.HI_PROPOSE,
                                "idx": self.queue_idx
                            })
                    case {"type": Matchmaking.START_REQ, "dst": target_id} if target_id == self._client_id:
                        # If someone wants to begin a match, accept if we haven't accepted yet
                        if not self.found_opponent.is_set():
                            self.found_opponent.set()
                            await self.do_publish(Topics.MATCHMAKING, {
                                "type": Matchmaking.START_ACK,
                                "dst": sender_id
                            })
                    case {"type": Matchmaking.START_ACK, "dst": target_id} if target_id == self._client_id:
                        # If someone accepts a match, accept as well and move on
                        if not self.game_begins.is_set():
                            # The side that receives the request is the first to move
                            self.my_turn = not self.found_opponent.is_set()
                            self.opponent_id = sender_id
                            self.found_opponent.set()
                            self.game_begins.set()
                            await self.do_publish(Topics.MATCHMAKING, {
                                "type": Matchmaking.START_ACK,
                                "dst": sender_id
                            })
                            await self.do_unsubscribe(Topics.MATCHMAKING)
                    case _:
                        debug_print(f"WARNING: '{self._client_id}' got unknown message from '{sender_id}': '{payload.decode()}'")
            case _:
                debug_print(f"WARNING: '{self._client_id}' got message from unknown topic '{topic}': '{payload.decode()}'")

    async def do_on_disconnect(self, packet, exc=None):
        pass

    async def do_on_subscribe(self, mid, qos, properties):
        self.subscribe_queue.put_nowait(None)

    async def do_on_unsubscribe(self, mid, qos):
        self.unsubscribe_queue.put_nowait(None)

    # Do the things
    async def do_subscribe(self, topic, specifier="#", qos=1):
        self.subscribe(f"{topic}/{specifier}", qos)
        await self.subscribe_queue.get()

    async def do_unsubscribe(self, topic, specifier="#", qos=1):
        self.subscribe(f"{topic}/{specifier}", qos)
        await self.unsubscribe_queue.get()

    async def do_publish(self, topic, data, qos=1):
        self.publish_dict.setdefault(topic, asyncio.Event()).clear()
        self.publish(f"{topic}/{self._client_id}", data, qos)
        await self.publish_dict[topic].wait()

    async def print_index(self):
        while not g_stop_evt.is_set():
            debug_print(f"Queue idx: {self.queue_idx}")
            await asyncio.sleep(1)

    # Doesn't do anything yet
    async def do_loop(self, stdscr):
        while not g_stop_evt.is_set():
            #if self.game_begins.is_set():
            #for i in range(9):
                #stdscr.addstr(i, 0, "Hello World")
            #stdscr.refresh()
            await asyncio.sleep(0.5)

    async def task_main(self, stdscr):
        await self.do_subscribe(Topics.MATCHMAKING)
        await self.do_publish(Topics.MATCHMAKING, {
            "type": Matchmaking.HI_PROPOSE,
            "idx": self.queue_idx
        })

        self.board_cells = [Cell(y, x, stdscr) for y, x in itertools.product(range(3), range(3))]
        for c in self.board_cells:
            c.draw()

        stdscr.refresh()

        while not self.game_begins.is_set() and not g_stop_evt.is_set():
            await asyncio.sleep(0)
        debug_print(f"my turn: {self.my_turn} other: {self.opponent_id}")

        g_stop_evt.set() # TEMPORARY

    async def mainloop(self, stdscr):
        async with asyncio.TaskGroup() as tg:
            task1 = tg.create_task(self.task_main(stdscr))
            task2 = tg.create_task(self.do_loop(stdscr))

    def stop_tasks(self):
        with self.task_lock:
            for t in self.running_tasks:
                t.cancel()

class Cell:
    def __init__(self, y, x, stdscr):
        tmp_y, tmp_x = stdscr.getmaxyx()
        self.h = tmp_y // 3 - 0
        self.w = tmp_x // 3 - 0
        assert self.h > 0
        assert self.w > 0
        self.side_y = min(self.w // 2, self.h)
        self.side_x = min(self.w, self.h * 2)
        self.y = y * self.h + max((self.h - self.side_y) // 2, 0)
        self.x = x * self.w + max((self.w - self.side_x) // 2, 0)
        self.window = stdscr.subwin(self.side_y, self.side_x, self.y, self.x)

    def draw(self, contents="o"):
        self.window.border()
        if contents == "x":
            for j in range(1, self.side_y - 1):
                for i in range(1, self.side_x - 1):
                    if i // 2 == j or i // 2 == self.side_y - j - 1:
                        self.window.addch(j, i, "#")
        elif contents == "o":
            for j in range(1, self.side_y - 1):
                for i in range(1, self.side_x - 1):
                    pos_x = (i - self.side_x / 2) / 2
                    pos_y = (j - self.side_y / 2) + 0.5
                    limit = self.side_y / 2 - 1
                    circle = limit ** 2 - (pos_y ** 2 + pos_x ** 2)
                    if circle > 0 and circle < (self.side_x / 6) ** 2:
                        self.window.addch(j, i, "#")
        else:
            pass
        self.window.refresh()

# Needs to be global so that the signal handler can cancel the async tasks
g_client = TicTacToeClient()

async def a_main(stdscr):
    await g_client.connect(BROKER_HOST, version=MQTT_VERSION)
    await g_client.mainloop(stdscr)
    await g_client.disconnect()

def ask_exit(*args):
    debug_print()
    g_stop_evt.set()
    g_client.stop_tasks()
    # Uncomment in case of deadlock
    #asyncio.get_event_loop().stop()

def main(stdscr):
    #logging.basicConfig(level=logging.NOTSET)
    logging.getLogger("asyncio").setLevel(logging.DEBUG)

    loop = asyncio.get_event_loop()

    loop.add_signal_handler(signal.SIGINT, ask_exit)
    loop.add_signal_handler(signal.SIGTERM, ask_exit)
    #loop.set_debug(True)

    loop.run_until_complete(a_main(stdscr))

if __name__ == "__main__":
    #main(None)
    curses.wrapper(main)
