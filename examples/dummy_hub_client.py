"""
Example to mimic the EagleDaddy Hub. Acts as both a Subscriber to its personal channel based on its ID.
"""
import sys
import json

sys.path.insert(0, '../')
import time
import logging
from passphrase import Passphrase
import paho.mqtt.client as mqtt
from comms import Message, MessageInfo, VALID_CMD

logging.basicConfig(level=logging.INFO, filename='hub.log')


class ConnectorId(Passphrase):
    def __init__(self) -> None:
        super().__init__(inputfile='english.txt')
        self.amount_n = 1
        self.amount_w = 3
        self.generate()
        self.separator = '-'

    def as_str(self):
        return str(self)


# CONNECTOR_ID = str(ConnectorId())
# DEVICE_ID = str(uuid.uuid4())

CONNECTOR_ID = "nonprepositionally-definitized-enlisted-711641"
DEVICE_NAME = "normal-dragon"
DEVICE_ID = "6b429ab7-8d25-4a9d-8419-897b1b4f4577"

ROOT_TOPIC = '/eagledaddy'
ANNOUNCE_TOPIC = ROOT_TOPIC + '/announce'

DUMMY_NODE_1 = {
    'id': 1,
    'address64': b'\x00\x13\xa2\x00A\xbd*z',
    'node_id': 'test0',
    'operating_mode': b'\x01',
    'network_id': b'\x7f\xff',
    'parent_device': b'\x00\x13\xa2\x00A\xbd3F'
}

DUMMY_NODE_2 = {
    'id': 2,
    'address64': b'\x00\x13\xa2\x00A\xb6%\xb5',
    'node_id': 'test1',
    'operating_mode': b'\x01',
    'network_id': b'\x7f\xff',
    'parent_device': b'\x00\x13\xa2\x00A\xbd3F'
}


def gen_message(params: dict) -> Message:
    """
    important that the original cmd is appended
    to payload
    """
    if "response" in params.keys():
        if isinstance(params['response'], VALID_CMD):
            cmd: VALID_CMD = params['response']
            params['response'] = cmd.value

    return Message(**params)


def node_discovery():
    global DUMMY_NODE_1, DUMMY_NODE_2
    print("Discovering...")
    time.sleep(2)
    nodes = [DUMMY_NODE_1, DUMMY_NODE_2]

    for idx, node in tuple(enumerate(nodes)):
        for k, v in tuple(node.items()):
            if isinstance(v, (bytes, bytearray)):
                nodes[idx][k] = v.hex()
    return nodes


class HubClient(mqtt.Client):
    def __init__(self):
        transport = 'tcp'
        self.id = DEVICE_ID
        self.connect_id = CONNECTOR_ID
        self.hub_name = DEVICE_NAME
        super().__init__(transport=transport, client_id=self.id)

    def _parse_incoming_message_and_reply(self, msg: Message):
        cmd = msg.get('cmd', None)
        if cmd:
            r = dict()
            r['cmd'] = cmd
            if cmd == VALID_CMD.PING:
                r['response'] = VALID_CMD.PONG
                logging.info("REPLY: PONG")

            elif cmd == VALID_CMD.ANNOUNCE_ACK:
                logging.info("ANNOUNCE ACK recieved")

            elif cmd == VALID_CMD.DISCOVERY:
                results = node_discovery()
                results_j = json.dumps(results)
                r['response'] = results_j
                logging.info(f"REPLY: {results_j}")

            else:
                r['response'] = VALID_CMD.UNKNOWN
                logging.warning(f"UNKNOWN COMMAND: {cmd}")

            reply = gen_message(r)
            info = self.send(reply)
            logging.info(f"Reply: {info}")

    def on_message(self, client, userdata, msg: bytes):
        print(msg.payload)
        msg = Message.decode(msg)
        self._parse_incoming_message_and_reply(msg)

    def on_publish(self, client, userdata, mid):
        pass

    def on_subscribe(self, client, userdata, mid, granted_qos):
        print(f'subscribed to dedicated channel: {ROOT_TOPIC}/{DEVICE_ID}')

    @property
    def listening_channel(self):
        return f"{ROOT_TOPIC}/{DEVICE_ID}/cloud"

    @property
    def talking_channel(self):
        return f"{ROOT_TOPIC}/{DEVICE_ID}"

    def run(self):
        port = 1883
        host = "127.0.0.1"
        self.connect(host=host, port=port)
        self.subscribe(self.listening_channel)

        self.announce()
        self.loop_forever()

    def announce(self):
        """
        send announcement to broker
        """
        msg = Message(hub_id=self.id,
                      connect_passphrase=self.connect_id,
                      hub_name=self.hub_name)

        self.send(msg, channel=ANNOUNCE_TOPIC)

    def stop(self):
        self.loop_stop()

    def send(self, msg: Message, channel=None):
        channel = self.talking_channel if channel is None else channel
        info = self.publish(channel, msg.encode(), qos=2)
        return info

    def publish(self, *args, **kwargs):
        info = super().publish(*args, **kwargs)
        return MessageInfo(info)


if __name__ == '__main__':
    import time
    print(f"Device ID: {DEVICE_ID}")
    print(f"CONNECT_ID: {CONNECTOR_ID}")
    hub = HubClient()
    hub.run()
