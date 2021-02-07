"""
The main MQTT Manager for EagleDaddy Cloud.


Subscribes to a channel disignated on redis for commands
that need to be sent.

Handles stateless communication for arbitrary commands sent
from web app and publishes to appropriate channels on MQTT.

The results of MQTT is updated on the database, where the webapp reads the changes.

It is a cyclical pattern of

                     ▲ |
                     | ▼
Web App -> Redis -> MQTT Manager -> Database -> WebApp


MQTT.

Channel dedicated to speaking to individual device is:
/eagledaddy/<hub_id>

Channel dedicated to l
"""
import sys
import os
import django
sys.path.insert(0, sys.path[0] + "/..")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "EagleDaddyCloud.settings")
django.setup()

import logging
import json
from typing import List, Union
import importlib
import uuid
import paho.mqtt.client as mqtt
import redis

from utils.utils import is_iter, lazy_property, make_iter
from django.utils import timezone
from utils.utils import Singleton
from broker.models import ClientHubDevice, NodeModule

from EagleDaddyCloud.settings import CONFIG
from comms import Message, MessageInfo, VALID_CMD

logging.basicConfig(level=logging.INFO, filename='channel_manager.log')

_REDIS_HOSTNAME = "redis"
_REDIS_PORT = 6379

_REDIS_CMD_CHANNEL = "redis/eagledaddy/cmds"
_REDIS_TIMEOUT = 0.01


class _MessageCallback:
    def __init__(self, manager, channel, msg: Message) -> None:
        self.manager = manager
        self.channel = channel
        self.msg = msg

    @classmethod
    def callback(cls, manager, obj, msg):
        channel: str = msg.topic
        message: Message = Message.decode(msg)
        obj = cls(manager, channel, message)
        obj.process()

    def process(self):
        raise NotImplementedError()


class DirectMessage(_MessageCallback):
    def process(self):
        # get hub record for this message
        hub = self.manager.objects.filter(
            hub_id=uuid.UUID(self.device_id)).first()
        if not hub:
            #TODO: handle what happens if we get a direct message from a
            # hub the cloud is subscribed too, but it doesn't exist in database..whoops
            logging.error(
                "Can not handle message from a hub that isn't in database")
            return

        # cmd will be present, if hub is responding to a previous command
        cmd = self.msg.get('cmd', None)
        if not cmd:
            # this is a direct unsolicited command from hub
            #TODO: handle unsolicited response from hub.
            logging.error(
                "A direct unsolicited response from hub: {self.device_id}")
            return

        if cmd == VALID_CMD.PONG:
            logging.info("{self.device_id} responded to PING")

        elif cmd == VALID_CMD.DISCOVERY:
            # expecting json valid list of node information
            # as described in [...make some reference here...]
            nodes = self.msg.get('response', None)
            logging.info(f"Found nodes: {nodes}")
            if not nodes:
                #TODO: handle what to do if no nodes are discovered
                # maybe create a database for each valid command and save reponse?
                return

            for node in json.loads(nodes):
                NodeModule.objects.update_or_create(hub=hub,
                                                    address=node['address64'],
                                                    defaults={
                                                        'address':
                                                        node['address64'],
                                                        'node_id':
                                                        node['node_id'],
                                                        'operating_mode':
                                                        node['operating_mode'],
                                                        'network_id':
                                                        node['network_id'],
                                                        'hub_node_id':
                                                        node['parent_device']
                                                    })
                logging.info(f"created node: {node['address64']}")

    @lazy_property
    def device_id(self):
        split = self.channel.split('/')
        if len(split) < 3:
            return "ERROR_DEVICE_ID"
        return split[2]


class Announce(_MessageCallback):
    def process(self):
        """
        Used to either update a current hub device's checkin time
        or to add a new hub to the database
        """
        if 'hub_id' not in self.msg.keys(
        ) or 'connect_passphrase' not in self.msg.keys():
            # send back to client the error of their ways
            pass
        hub_id = uuid.UUID(self.msg['hub_id'])
        connect_passphrase = self.msg['connect_passphrase']
        hub_name = self.msg['hub_name']

        #TODO: handle if more than one is found, very unlikely to happen
        existing_hub = self.manager.objects.filter(hub_id=hub_id).first()
        logging.info(existing_hub)
        if not existing_hub:
            logging.info('hub not found, adding')
            new_hub = ClientHubDevice(hub_id=hub_id,
                                      connect_passphrase=connect_passphrase,
                                      hub_name=hub_name,
                                      last_checkin=timezone.now())
            new_hub.save()

            # create dedicated listening channel
            logging.info(
                f'subscribing to individual channel: /eagledaddy/{hub_id}')
            self.manager.message_callback_add(f"/eagledaddy/{hub_id}",
                                              DirectMessage.callback)
            existing_hub = new_hub
        else:
            # found it, update last_checkin
            logging.info(f'hub [{existing_hub.hub_id}] checking in....')
            existing_hub.last_checking = timezone.now()
            existing_hub.save()

        # send acknowledgement back that announced was recieved
        self.manager.send_hub_command(existing_hub, VALID_CMD.ANNOUNCE_ACK)


class ChannelManager(mqtt.Client, metaclass=Singleton):
    """
    Handles communication with the local MQTT Broker.
    Subscribes and publishes messages on topics according
    to connected clients/hubs.
    """
    announce_channel = CONFIG.mqtt.root_channel + '/announce'

    # will log specific channels that is registered under /#
    valid_self_listening_channels = []

    def __init__(self):

        protocol_name = CONFIG.mqtt.protocol
        mod = importlib.import_module('paho.mqtt.client')
        protocol = getattr(mod, protocol_name, None)
        transport = CONFIG.mqtt.transport

        super().__init__(client_id="channel_manager",
                         protocol=protocol,
                         clean_session=False,
                         transport=transport)

    def load_subscriptions(self):
        for hub in self.objects.all():
            logging.info(f'subscribing............. /eagledaddy/{hub.hub_id}')
            self.message_callback_add(hub.listening_channel,
                                      DirectMessage.callback)

    @lazy_property
    def objects(self):
        return ClientHubDevice.objects

    def on_message(self, client, userdata, message):
        if 'cloud' in message.topic:  # this is outgoing message, ignore
            pass

        elif message.topic in self.valid_self_listening_channels:
            logging.warning(
                f"Message on specific channel: `{message.topic}`:`{message.payload}`"
            )
        else:
            # ignore everything else
            logging.error(
                f"Direct Message: `{message.topic}`:`{message.payload}`")

    def on_log(self, client, obj, level, string):
        logging.log(level, string)

    # def on_publish(self, client, obj, mid):
    #     logging.info(f"ON_PUB {obj}:{mid}")

    # def on_subscribe(self, client, obj, mid, granted_qos):
    #     logging.info(f"ON_SUB {obj}:{mid}:{granted_qos}")

    def send_hub_command(self, hubs, cmd: VALID_CMD):

        logging.info(f"Hub is connected: {self.is_connected()}")
        if not is_iter(hubs):
            hubs = make_iter(hubs)
        message = Message(cmd=cmd.value)

        hub_objs = list()
        for hub in hubs:
            if isinstance(hub, str):
                h = self.objects.filter(hub_name=hub).first()
                if not h:
                    continue
                hub_objs.append(h)
            hub_objs.append(hub)
        return self._send_hub_data(hub_objs, message)

    def _send_hub_data(self, hubs: Union[List[ClientHubDevice],
                                         ClientHubDevice], msg: Message):
        if not is_iter(hubs):
            hubs = make_iter(hubs)

        msg_infos = dict()
        for hub in hubs:
            logging.info(
                f"Sending {VALID_CMD(msg['cmd']).name} to {hub.hub_id}")
            msg_info = MessageInfo(
                self.publish(hub.dedicated_channel, msg.encode()))
            msg_infos[hub.hub_name] = msg_info.describe()
        return msg_infos

    def clear(self):
        """clear all hub clients"""
        return [x.delete() for x in self.objects.all()]

    def run(self):
        port = CONFIG.mqtt.port
        host = CONFIG.mqtt.host
        qos = CONFIG.mqtt.qos

        self.message_callback_add(self.announce_channel, Announce.callback)
        self.connect(host=host, port=int(port))
        logging.info("Manager started...")
        self.loop_start()

        logging.info(f"Manager listening... {CONFIG.mqtt.root_channel}/#")
        self.subscribe(f"{CONFIG.mqtt.root_channel}/#", int(qos))

        logging.info(f"Loading verified subscriptions")
        self.load_subscriptions()

    def stop(self):
        self.loop_stop()

    def handle_proxy_message(self, msg: dict):
        if 'data' not in msg.keys():
            logging.error("Message from proxy server not in correct format")
            return
        try:
            data = json.loads(msg.get('data'))
        except:
            logging.error(f"Unable to correctly parse proxy message, {msg}")
            return

        # here we assume (not the time to check) each key is a hub_id
        # that has been already registered with databas
        # the entire payload is the value of each key, simply search for this hub
        # from database and send it
        for hub_id, payload in data.items():
            try:
                hub_id = uuid.UUID(hub_id)
            except ValueError as e:
                logging.error(e)
                continue

            hub = ClientHubDevice.objects.filter(hub_id=hub_id).first()
            if not hub:
                logging.error(
                    f"No such hub exists in database to send data to, error hub id: {hub_id}"
                )
                continue
            message = VALID_CMD(int(payload))
            self.send_hub_command(hub, message)


if __name__ == "__main__":
    rclient = redis.Redis(host=_REDIS_HOSTNAME, port=_REDIS_PORT, db=0)
    sub = rclient.pubsub()
    sub.subscribe(_REDIS_CMD_CHANNEL)
    logging.info(f"Subscribed to proxy server channel, {_REDIS_CMD_CHANNEL}")

    manager = ChannelManager()
    manager.run()

    while True:
        msg = sub.get_message(timeout=_REDIS_TIMEOUT)
        if not msg:
            continue
        manager.handle_proxy_message(msg)