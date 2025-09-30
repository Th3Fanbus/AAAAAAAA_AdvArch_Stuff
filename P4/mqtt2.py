import socket
import asyncio
import logging

from tornado.ioloop import IOLoop,PeriodicCallback

import gmqtt

import gmqtt.mqtt.constants

class GMQTT(object):
    def __init__(self):
        self.log =  logging.getLogger(__name__)
        self.log.setLevel(logging.DEBUG)
        self.mqtt_broker_host = "localhost"
        self.mqtt_broker_port = 1883
        self.dst_topic = "TEST/#"

        self.period_callback = None

        self.loop = IOLoop.instance()

        ## self.loop.asyncio_loop ==
        mqtt_client = gmqtt.Client(client_id="xxxx", retry_deliver_timeout=1)
        mqtt_client.on_connect = self.on_connect
        mqtt_client.on_message = self.on_message
        mqtt_client.on_disconnect = self.on_disconnect
        #mqtt_client.on_subscribe = self.on_subscribe
        mqtt_client.set_auth_credentials("guest", "guest")
        self.mqtt_client = mqtt_client
        self.index = 0


    async def period_check(self):
        '''
            send msg periodically
        '''
        print("send")
        if self.mqtt_client.is_connected:
            print("sending")
            self.mqtt_client.publish(self.dst_topic, f"Hello:{self.index}".encode() )
            self.index +=1
            print("sent")

    def on_message(self, client, topic, payload, qos, properties):
        print(f'MQTT.Recv {client._client_id}] TOPIC: {topic} PAYLOAD: {payload} QOS: {qos} PROPERTIES: {properties}')

    def on_connect(self, client, flags, rc, properties):
        print('[MQTT.CONNECTED {}]'.format(client._client_id))
        self.mqtt_client.subscribe( self.dst_topic )

    def on_disconnect(self, client, packet, exc=None):
        print('[MQTT.DISCONNECTED {}]'.format(client._client_id))

    async def unreg(self):
        print("unreg")
        if self.mqtt_client.is_connected:
            print("unregging")
            self.mqtt_client.unsubscribe( self.dst_topic )
            await self.mqtt_client.disconnect()

    async def reg(self):
        print("connect")
        await self.mqtt_client.connect(self.mqtt_broker_host, version=gmqtt.mqtt.constants.MQTTv311)
        print("connected")
        if not self.period_callback :
            self.period_callback = PeriodicCallback(self.period_check,
                                                    callback_time=1000) #Unit：milliseconds
        print("callback")
        if not self.period_callback.is_running():
            self.period_callback.start()
        print("callbacked")

if __name__ == "__main__":
    #logging.basicConfig(level=logging.NOTSET)
    c = GMQTT()
    c.loop.run_sync(c.reg)
    c.loop.call_later(10, c.unreg)
    c.loop.start()
