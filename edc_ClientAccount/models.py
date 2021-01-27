from django.db import models

from django.contrib.auth import get_user_model


class ClientAccount(models.Model):
    """
    Represents the main entity of an account
    """
    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE, related_name='account')



