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
/eagledaddy/<hub_id>/cloud

Channel dedicated to listening from devices is
/eagledaddy/<hub_id>
"""

import json
import logging
import uuid
import time
from pathlib import Path
from passphrase import Passphrase
from edcomms import EDChannel, EDClient, EDPacket, EDCommand, MessageCallback

logging.basicConfig(level=logging.DEBUG, filename="hub.log")

_BROKER_HOST = "ed.qubixat.com"
_BROKER_PORT = 1883

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

DUMMY_NODE_3 = {
    'id': 4,
    'address64': b'\x00\x13\xa2\x00A\xb6%\xc8',
    'node_id': 'deer_feeder_01',
    'operating_mode': b'\x01',
    'network_id': b'\x7f\xff',
    'parent_device': b'\x00\x13\xa2\x00A\xbd3F'
}


class ConnectorId(Passphrase):
    def __init__(self, n=1, w=3) -> None:
        super().__init__(inputfile='english.txt')
        self.amount_n = n
        self.amount_w = w
        self.generate()
        self.separator = '-'

    def as_str(self):
        return str(self)


def get_device_info():
    """
    gets mock information regarding
    this hub client.

    Returns:
        (CONNECTOR_ID, DEVICE_ID, DEVICE_NAME)
    """
    pwd = Path(__file__).parent / "device.info"
    if not pwd.is_file():
        params = {
            "connect_passphrase": str(ConnectorId()),
            "hub_id": str(uuid.uuid4()),
            "hub_name": str(ConnectorId(w=2, n=0))
        }
        with open(pwd, 'w') as f:
            json.dump(params, f)

    device_info = json.load(pwd.open())

    return device_info


class HubMessageCallback(MessageCallback):
    def process(self):
        packet: EDPacket = self.packet
        hub_id = packet.sender_id
        if not packet.command:
            logging.warning(
                "Hub recieved message from cloud with no Command defined.")
            return

        c = packet.command
        if c == EDCommand.ping:
            packet = self.handle_ping()

        elif c == EDCommand.discovery:
            packet = self.handle_discovery()
        else:
            packet = self.handle_unknown()

        channel = self.client.talking_channel
        self.client.publish(channel, packet)

    def handle_discovery(self):
        global DUMMY_NODE_1, DUMMY_NODE_2, DUMMY_NODE_3

        print("Discovering...")
        time.sleep(2)
        nodes = [DUMMY_NODE_1, DUMMY_NODE_2, DUMMY_NODE_3]

        for idx, node in tuple(enumerate(nodes)):
            for k, v in tuple(node.items()):
                if isinstance(v, (bytes, bytearray)):
                    nodes[idx][k] = v.hex()

        return self.client.create_packet(EDCommand.discovery, payload=nodes)

    def handle_ping(self):
        return self.client.create_packet(EDCommand.pong, None)

    def handle_unknown(self):
        return self.client.create_packet(EDCommand.unknown, None)


class HubClient(EDClient):
    announce_channel = EDChannel('announce/')
    listening_channel = None
    talking_channel = None
    _device_info = None

    def init(self):
        super().init()
        self.talking_channel = EDChannel(f"{self.client_id}")

        self.listening_channel = EDChannel(f"{self.client_id}/cloud")
        self.add_subscription(self.listening_channel,
                              callback=HubMessageCallback)

    def run(self):
        self.init()
        self.loop_start()

        self.announce()
        while True:
            pass

    def announce(self):
        device_info = self._device_info
        announce_packet = self.create_packet(EDCommand.announce,
                                             payload=device_info)
        self.publish(self.announce_channel, announce_packet)


if __name__ == "__main__":
    device_info = get_device_info()

    device_id = device_info.get('hub_id')
    connector_id = device_info.get('connect_passphrase')
    device_name = device_info.get('hub_name')
    logging.info(f"Device ID: {device_id}")
    logging.info(f"Connect ID: {connector_id}")
    logging.info(f"Device Name: {device_name}")

    hub = HubClient(uuid.UUID(device_id), host=_BROKER_HOST, port=_BROKER_PORT)
    hub._device_info = device_info
    try:
        hub.run()
    except KeyboardInterrupt:
        hub.loop_stop()
