import logging
from edcomms import EDChannel
from django.db import models
from django.utils import timezone

from EagleDaddyCloud.settings import CONFIG
from ClientAccount.models import ClientAccount


class ClientHubDevice(models.Model):
    """
    Represents a virtual copy
    of a physical Eagle Daddy Hub device
    """
    account = models.ForeignKey(ClientAccount,
                                on_delete=models.CASCADE,
                                null=True,
                                related_name='account')
    connect_passphrase = models.CharField(max_length=1028)
    last_checkin = models.DateTimeField(default=timezone.now)
    hub_name = models.CharField(max_length=128, null=True)
    hub_id = models.UUIDField(null=False)
    current_state = models.CharField(max_length=32, default="")
    last_message = models.CharField(max_length=2048, null=True)

    @property
    def dedicated_channel(self) -> EDChannel:
        root = CONFIG.mqtt.root_channel
        return EDChannel(f"{self.hub_id}/cloud/", root=root)

    @property
    def listening_channel(self) -> EDChannel:
        root = CONFIG.mqtt.root_channel
        return EDChannel(f"{self.hub_id}/", root=root)


    def _get_associated_flags_record(self):
        flags: CommandResponseFlag = CommandResponseFlag.objects.filter(hub=self).first()
        if not flags:
            logging.critical("hub does not have command ready flags record, IPC will not work as intended")
            raise Exception()

        return flags

    def _set_or_get_flag(self, flagname, set_):
        flags = self._get_associated_flags_record()
        if set_ is None:
            return flags.__dict__[flagname]

        flags.__dict__[flagname] = set_
        flags.save()

    def discover_ready(self, set_=None):
        return self._set_or_get_flag('discover_ready', set_=set_)

    def diagnostics_ready(self, set_=None):
        return self._set_or_get_flag('diagnostic_ready', set_=set_)


class CommandResponseFlag(models.Model):
    """
    A table that acts much like a bitflag.
    Each row is attached to a single hub with the columns
    representing a command ready. By default,
    each column is set to False. Only the MQTT manager
    has (should) the ability to toggle the flags for each
    command indicating the response is ready for retrieval by the web
    app.

    """
    hub = models.ForeignKey(ClientHubDevice, null=False, on_delete=models.CASCADE)
    discover_ready = models.BooleanField(default=False)
    diagnostic_ready = models.BooleanField(default=False)

class CommandDiagnosticsResponse(models.Model):
    """
    Table to store raw xml output from hub
    """
    hub = models.ForeignKey(ClientHubDevice, null=False, on_delete=models.CASCADE)
    report = models.JSONField()

class NodeModule(models.Model):
    """
    Represents the individual remote nodes
    that operate on the DigiMesh network of a 
    Hub Device.
    """
    hub = models.ForeignKey(ClientHubDevice,
                            null=False,
                            on_delete=models.CASCADE,
                            related_name='node')

    address = models.CharField(max_length=16)
    hub_node_id = models.CharField(max_length=16)
    node_id = models.CharField(max_length=512)
    operating_mode = models.CharField(max_length=512)
    network_id = models.CharField(max_length=512)



    def __str__(self) -> str:
        return repr(self)

    def __repr__(self) -> str:
        return f"<Node {self.node_id}>"

