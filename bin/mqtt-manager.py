import logging
from typing import Any, Dict, List
import redis
import sys
import json
import os
import django
import uuid
from edcomms import EDChannel, EDClient, EDPacket, EDCommand, MessageCallback, _ROOT_CHANNEL

sys.path.insert(0, sys.path[0] + "/..")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "EagleDaddyCloud.settings")
django.setup()

from django.utils import timezone
from EagleDaddyCloud.settings import CONFIG
from utils.utils import is_iter, lazy_property, make_iter
from broker.models import ClientHubDevice, CommandDiagnosticsResponse, CommandResponseFlag, NodeModule

#TODO: convert this in edcomms package to change root channel
# globally
_ROOT_CHANNEL = CONFIG.mqtt.root_channel

logging.basicConfig(level=logging.DEBUG, filename="channel_manager.log")

_REDIS_HOSTNAME = "redis"
_REDIS_PORT = 6379

_REDIS_CMD_CHANNEL = "redis/eagledaddy/cmds"
_REDIS_TIMEOUT = 0.01
_MANAGER_ID = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")


class DiretMessageCallback(MessageCallback):
    def process(self):
        hub_id = self.packet.sender_id
        hub: ClientHubDevice = self.client.objects.filter(
            hub_id=hub_id).first()

        if not hub:
            logging.error(
                "Can't handle message from hub that isn't in database")
            return

        cmd = self.packet.command
        if not cmd:
            # unsolicited response from hub, not sure how to handle this
            logging.warning("An unsolicited response from hub recieved")
            logging.warning(f"{self.packet.describe()}")
            return

        if cmd == EDCommand.pong:
            logging.debug("{self.packet.sender_id} responded to PING")

        elif cmd == EDCommand.discovery:

            # we are expecting nodes to a list of dictionaries
            nodes: List[Dict[str, Any]] = self.packet.payload
            logging.debug(f"Found nodes: {len(nodes)}")
            if not nodes:
                logging.info("No nodes found for {self.packet.sender_id}")
                return

            for node in nodes:
                defaults = {
                    'address': node['address64'],
                    'node_id': node['node_id'],
                    'operating_mode': node['operating_mode'],
                    'network_id': node['network_id'],
                    'hub_node_id': node['parent_device'],
                }

                result = NodeModule.objects.update_or_create(
                    hub=hub, address=node['address64'], defaults=defaults)
                logging.debug(f"Node creation, {result}, {node['address64']}")

            # logging.debug("setting discovery ready flag")
            # hub.discover_ready(True)
        
        elif cmd == EDCommand.diagnostics: 
            """ expecting a diagnostics report from hub """
            payload = self.packet.payload
            logging.info(payload)
            report_diag = json.loads(payload)
            report_status = CommandDiagnosticsResponse.objects.update_or_create(hub=hub, defaults={'hub': hub, 'report': report_diag})
            logging.debug(report_status)
            logging.debug("setting diagnostics flag")
            hub.diagnostics_ready(True)


class AnnounceCallback(MessageCallback):
    def process(self):
        """
        Announce channel is used by hubs to either checkin
        or register itself.
        """
        packet = self.packet
        payload = packet.payload
        logging.debug(f"payload recvd: {payload}")
        if 'hub_id' not in payload.keys(
        ) or 'connect_passphrase' not in payload.keys():
            logging.error("invalid announce packet format")
            return

        hub_id = uuid.UUID(payload.get('hub_id'))
        connect_passphrase = payload.get('connect_passphrase')
        hub_name = payload.get('hub_name')
        existing_hub = self.client.objects.filter(hub_id=hub_id).first()
        if not existing_hub:
            logging.info("Hub not found, creating new entry")
            new_hub = ClientHubDevice(hub_id=hub_id,
                                      connect_passphrase=connect_passphrase,
                                      hub_name=hub_name,
                                      last_checkin=timezone.now())
            new_hub.save()

            # attach new command response flag record to this  hub
            flags = CommandResponseFlag(hub=new_hub)
            flags.save()

            channel = EDChannel(f"{hub_id}/")

            logging.info(f"Subscribing to hubs' channel: {channel}")
            self.client.add_subscription(channel,
                                         callback=DiretMessageCallback)
            existing_hub = new_hub
        else:
            logging.info(f"{existing_hub.hub_id} checking in....")
            existing_hub.last_checking = timezone.now()
            existing_hub.save()

        # send acknowledgement back that announced was recieved
        packet = self.client.create_packet(EDCommand.ack, payload=None)
        self.client.publish(existing_hub.dedicated_channel, packet)


class ChannelManager(EDClient):
    def init(self):
        super().init()
        self.loop_start()

        announce_channel = EDChannel("announce/")

        # this automatically make main subscription: /<root>/#
        self.add_subscription(announce_channel, callback=AnnounceCallback)
        self.load_subscriptions()

    def run(self):
        self.init()

    @lazy_property
    def objects(self):
        return ClientHubDevice.objects

    def clear(self):
        return [x.delete() for x in self.objects.all()]

    def load_subscriptions(self):
        logging.info("loading subscriptions")
        for hub in self.objects.all():
            self.add_subscription(hub.listening_channel,
                                  callback=DiretMessageCallback)

    def send_packet(self, hubs, packet: EDPacket):
        if not is_iter(hubs):
            hubs = make_iter(hubs)

        msg_infos = dict()
        for hub in hubs:
            logging.info(f"sending {packet.command.name} to {hub.hub_id}")
            msg_info = self.publish(hub.dedicated_channel, packet)
            msg_infos[hub.hub_name] = msg_info
        return msg_infos

    def send_hub_command(self, hubs, cmd: EDCommand):
        if not is_iter(hubs):
            hubs = make_iter(hubs)

        hub_objs = list()
        for hub in hubs:
            if isinstance(hub, str):
                h = self.objects.filter(hub_name=hub).first()
                if not h:
                    continue
                hub_objs.append(h)
            hub_objs.append(hub)
        packet = self.create_packet(cmd, payload=None)
        return self.send_packet(hubs, packet)

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
            cmd = EDCommand(int(payload))
            self.send_hub_command(hub, cmd)


if __name__ == "__main__":
    rclient = redis.Redis(host=_REDIS_HOSTNAME, port=_REDIS_PORT, db=0)
    sub = rclient.pubsub()
    sub.subscribe(_REDIS_CMD_CHANNEL)
    logging.info(f"Subscribed to proxy server channel: {_REDIS_CMD_CHANNEL}")

    host = CONFIG.mqtt.host
    port = int(CONFIG.mqtt.port)
    manager = ChannelManager(_MANAGER_ID, host=host, port=port)
    manager.run()

    while True:
        msg = sub.get_message(timeout=_REDIS_TIMEOUT)
        if not msg:
            continue
        manager.handle_proxy_message(msg)