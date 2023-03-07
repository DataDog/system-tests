import pytest
from weblog_interface import *
from backend_interface import *
from wait_for_tcp_port import *


def test_forTraces(private_ip):
    print("TEST FOR TRACES:" + private_ip)
    print("Waiting for weblog available")
    wait_for_port(5985, private_ip, 60.0)
    print(private_ip + ": Weblog app is ready!")
    print("Making a request to weblog")
    request_uuid = make_get_request("http://" + private_ip + ":5985/")
    print(f"Http request done with uuid:", request_uuid)
    wait_backend_trace_id(request_uuid, 200.0)
