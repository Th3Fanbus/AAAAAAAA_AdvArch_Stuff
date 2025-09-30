import asyncio
import datetime
import os
import signal
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

# Host to try to connect to
BROKER_HOST = "localhost"

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

def on_connect(client, flags, rc, properties):
    print(f"MQTT.CONNECTED {client._client_id} FLAGS: {flags} RC: {rc} PROPERTIES: {properties}")
    client.subscribe("amq.direct", qos=1)

def on_message(client, topic, payload, qos, properties):
    print(f"MQTT.Recv {client._client_id}] TOPIC: {topic} PAYLOAD: '{payload.decode()}' QOS: {qos} PROPERTIES: {properties}")

def on_disconnect(client, packet, exc=None):
    print(f"MQTT.DISCONNECTED {client._client_id}")

def on_subscribe(client, mid, qos, properties):
    print(f"MQTT.SUSCRIBED {client._client_id} MID: {mid} QOS: {qos} PROPERTIES: {properties}")

def ask_exit(*args):
    print()
    g_stop_evt.set()

async def send_msg(client):
    if client.is_connected:
        #client.publish("amq.direct", str(time.time()).encode(), qos=1)
        client.publish("amq.direct", datetime.datetime.now().ctime().encode(), qos=1)
        client.publish("amq.direct", f"Hello:{4}".encode(), qos=1)

async def main():
    client = MQTTClient(cf_get_client_id())

    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    client.on_subscribe = on_subscribe

    client.set_auth_credentials("guest", "guest")
    await client.connect(BROKER_HOST, version=GMQTTConstants.MQTTv311)

    while not g_stop_evt.is_set():
        await send_msg(client)
        await asyncio.sleep(0.2)

    client.publish("amq.direct", str(time.time()), qos=1)

    await g_stop_evt.wait()
    await client.disconnect()

if __name__ == "__main__":
    #logging.basicConfig(level=logging.NOTSET)

    loop = asyncio.get_event_loop()

    loop.add_signal_handler(signal.SIGINT, ask_exit)
    loop.add_signal_handler(signal.SIGTERM, ask_exit)

    loop.run_until_complete(main())
