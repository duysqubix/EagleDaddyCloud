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
    def dedicated_channel(self):
        root = CONFIG.mqtt.root_channel
        return f"{root}/{self.hub_id}/cloud"

    @property
    def listening_channel(self):
        root = CONFIG.mqtt.root_channel
        return f"{root}/{self.hub_id}"


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
