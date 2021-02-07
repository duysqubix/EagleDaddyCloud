"""
A universal comms library that can be used by both EagleDaddyCloud
to communicate with Hubs and for Hubs to communicate with Eagle Daddy Cloud.
"""

import json
import paho.mqtt.client as mqtt
from enum import IntEnum


class Message(dict):
    def encode(self) -> str:
        return json.dumps(self)

    @classmethod
    def decode(cls, msg: mqtt.MQTTMessage):
        params = json.loads(msg.payload)
        return cls(**params)


class MessageInfo(mqtt.MQTTMessageInfo):
    def __init__(self, parentobj):
        super().__init__(parentobj.mid)

    def describe(self):
        return {
            'rc': mqtt.error_string(self.rc),
            'mid': f'MessageId: {self.mid}'
        }


class VALID_CMD(IntEnum):
    UNKNOWN = -2
    NACK = -1
    ACK = 0
    PING = 1
    PONG = 2
    DIAG = 3
    DISCOVERY = 4
    ANNOUNCE_ACK = 5