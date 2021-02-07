"""
The main MQTT broker for EagleDaddy Cloud
"""
import logging
from typing import List, Union
import importlib

import uuid
import paho.mqtt.client as mqtt
from utils.utils import is_iter, lazy_property, make_iter

from EagleDaddyCloud.settings import CONFIG

from django.utils import timezone
from edc_HubDevice.models import ClientHubDevice
from comms import Message, MessageInfo, VALID_CMD

logging.basicConfig(level=logging.INFO, filename='channel_manager.log')


class _MessageCallback:
    def __init__(self, client, channel, msg: Message) -> None:
        self.client = client
        self.channel = channel
        self.msg = msg

    @classmethod
    def callback(cls, client, obj, msg):
        channel: str = msg.topic
        message: Message = Message.decode(msg)
        obj = cls(client, channel, message)
        obj.process()

    def process(self):
        raise NotImplementedError()


class DirectMessage(_MessageCallback):
    def process(self):
        # update last_message with current one

        # cmd will be present, if hub is responding to a previous command
        cmd = self.msg.get('cmd', None)
        if not cmd:
            # this is a direct unsolicited command from hub
            #TODO: handle unsolicited response from hub.
            return

        if cmd == VALID_CMD.PONG:
            logging.info("{self.device_id} responded to PING")

        elif cmd == VALID_CMD.DISCOVERY:
            # expecting json valid list of node information
            # as described in [...make some reference here...]
            response = self.msg.get('response', None)
            print(response)

    @property
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
        existing_hub = self.client.hub.objects.filter(hub_id=hub_id).first()
        print(existing_hub)
        if not existing_hub:
            print('hub not found, adding')
            new_hub = ClientHubDevice(hub_id=hub_id,
                                      connect_passphrase=connect_passphrase,
                                      hub_name=hub_name,
                                      last_checkin=timezone.now())
            new_hub.save()

            # create dedicated listening channel
            print('creating listening channel')
            self.client.message_callback_add(f"/eagledaddy/{hub_id}",
                                             DirectMessage.callback)
            existing_hub = new_hub
        else:
            # found it, update last_checkin
            print(f'hub [{existing_hub.hub_id}] checking in....')
            existing_hub.last_checking = timezone.now()
            existing_hub.save()

        # send acknowledgement back that announced was recieved
        self.client.send_hub_command(existing_hub, VALID_CMD.ANNOUNCE_ACK)


class ChannelManager(mqtt.Client):
    """
    Handles communication with the local MQTT Broker.
    Subscribes and publishes messages on topics according
    to connected clients/hubs.
    """
    ANNOUNCE_CHANNEL = CONFIG.mqtt.root_channel + '/announce'

    def __init__(self):
        protocol_name = CONFIG.mqtt.protocol
        mod = importlib.import_module('paho.mqtt.client')
        protocol = getattr(mod, protocol_name, None)
        transport = CONFIG.mqtt.transport

        super().__init__(client_id="channel_manager",
                         protocol=protocol,
                         clean_session=False,
                         transport=transport)

    @lazy_property
    def hub(self):
        return ClientHubDevice

    def on_message(self, client, userdata, message):
        logging.warning(f"UNHANDLED CHANNEL {message.topic}:{message.payload}")

    def on_log(self, client, obj, level, string):
        logging.log(level, string)

    def on_publish(self, client, obj, mid):
        logging.info(f"ON_PUB {obj}:{mid}")

    def on_subscribe(self, client, obj, mid, granted_qos):
        logging.info(f"ON_SUB {obj}:{mid}:{granted_qos}")

    def send_hub_command(self, hubs: Union[List[ClientHubDevice],
                                           ClientHubDevice], cmd: VALID_CMD):
        if not is_iter(hubs):
            hubs = make_iter(hubs)
        message = Message(cmd=cmd.value)

        return self._send_hub_data(hubs, message)

    def _send_hub_data(self, hubs: Union[List[ClientHubDevice],
                                         ClientHubDevice], msg: Message):
        if not is_iter(hubs):
            hubs = make_iter(hubs)

        msg_infos = dict()
        for hub in hubs:
            msg_info = MessageInfo(
                self.publish(hub.dedicated_channel, msg.encode()))
            msg_infos[hub.hub_name] = msg_info.describe()
        return msg_infos

    def clear(self):
        """clear all hub clients"""
        return [x.delete() for x in self.hub.objects.all()]

    def run(self):
        port = CONFIG.mqtt.port
        host = CONFIG.mqtt.host
        qos = CONFIG.mqtt.qos

        self.message_callback_add(self.ANNOUNCE_CHANNEL, Announce.callback)
        self.connect(host=host, port=int(port))
        self.loop_start()

        self.subscribe(f"{CONFIG.mqtt.root_channel}/#", int(qos))

    def stop(self):
        self.loop_stop()