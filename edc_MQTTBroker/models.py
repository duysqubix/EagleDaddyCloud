from django.db import models
from django.utils import timezone

from edc_HubDevice.models import ClientHubDevice


class Topic(models.Model):
    """
    stores simple topic strings
    """
    topic = models.CharField(max_length=2048)


class Channel(models.Model):
    """
    channel information linking both account
    and hub device
    """
    topic = models.OneToOneField(Topic, on_delete=models.CASCADE)
    hub = models.OneToOneField(ClientHubDevice, on_delete=models.CASCADE)


class AnnounceMessage(models.Model):
    """
    Table for storing device announcements
    """
    hub_id = models.UUIDField(null=False)  # id of physical hub
    connect_passphrase = models.CharField(max_length=1028)  # passphrase used to connect hub <--> account
    last_checkin = models.DateTimeField(default=timezone.now)
