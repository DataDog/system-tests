from django.db import models
from django.contrib.auth.models import  AbstractUser



class CustomUser(AbstractUser):
    id = models.CharField(max_length=255, primary_key=True)
    class Meta:
        managed = True
        app_label = "app"
