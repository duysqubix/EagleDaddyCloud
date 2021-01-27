from django.db import models
from edc_ClientAccount.models import ClientAccount


class ClientHubDevice(models.Model):
    """
    Represents an virtual copy
    of a physical Eagle Daddy Hub device
    """
    hub_id = models.UUIDField(null=False)
    account = models.ForeignKey(ClientAccount, on_delete=models.CASCADE, null=True, related_name='hub')

