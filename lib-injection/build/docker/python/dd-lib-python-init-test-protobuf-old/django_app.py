import os
import signal
import sys

from django.http import HttpResponse
from django.urls import path

import addressbook_pb2


def handle_sigterm(signo, sf):
    sys.exit(0)


signal.signal(signal.SIGTERM, handle_sigterm)


filepath, extension = os.path.splitext(__file__)
ROOT_URLCONF = os.path.basename(filepath)
DEBUG = False
SECRET_KEY = "fdsfdasfa"
ALLOWED_HOSTS = ["*"]


def index(request):
    # Do some stuff with the protobuf
    person = addressbook_pb2.Person()
    person.id = 1234
    person.name = "John Doe"
    person.email = "john@ibm.com"

    print(person)

    return HttpResponse("test")


urlpatterns = [
    path("", index),
]
