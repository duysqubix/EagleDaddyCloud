"""
The main MQTT broker for EagleDaddy Cloud
"""
import importlib
import paho.mqtt.client as mqtt

from EagleDaddyCloud.settings import CONFIG


class _MessageCallback:
    def __init__(self, client, obj, msg) -> None:
        self.client = client
        self.obj = obj
        self.msg = msg

    @classmethod
    def callback(cls, client, obj, msg):
        obj = cls(client, obj, msg)
        obj.process()

    def process(self):
        raise NotImplementedError()


class DirectMessage(_MessageCallback):
    def process(self):
        print(f'Comms with: {self.device_id}: rx: {self.msg.payload}')

    @property
    def device_id(self):
        split = self.msg.topic.split('/')
        return split[-1]


class AnnounceMessage(_MessageCallback):
    def process(self):
        print(f'Announcment msg: {self.msg.payload}')


class ChannelManager(mqtt.Client):
    """
    Handles communication with the local MQTT Broker.
    Subscribes and publishes messages on topics according
    to connected clients/hubs.
    """
    def __init__(self):
        protocol_name = CONFIG.mqtt.protocol
        mod = importlib.import_module('paho.mqtt.client')
        protocol = getattr(mod, protocol_name, None)
        transport = CONFIG.mqtt.transport

        super().__init__(clean_session=True,
                         protocol=protocol,
                         transport=transport)

    def on_message(self, client, userdata, message):
        print(f"UNHANDLED CHANNEL {message.topic}:{message.payload}")

    def on_log(self, client, obj, level, string):
        # print(f"ON_LOG {client}:{obj}:{level}:{string}")
        pass

    def on_publish(self, client, obj, mid):
        print(f"ON_PUB {obj}:{mid}")

    def on_subscribe(self, client, obj, mid, granted_qos):
        print(f"ON_SUB {obj}:{mid}:{granted_qos}")

    def run(self):
        port = CONFIG.mqtt.port
        host = CONFIG.mqtt.host

        self.message_callback_add('/eagledaddy/announce',
                                  AnnounceMessage.callback)
        self.connect(
            host=host,
            port=int(port),
        )
        self.loop_start()

        self.subscribe("/eagledaddy/#", 0)

    def stop(self):
        self.loop_stop()