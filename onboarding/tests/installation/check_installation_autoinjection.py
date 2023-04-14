import pytest
from weblog_interface import *
from backend_interface import *
from wait_for_tcp_port import *


def test_forTraces(ip):
    ''' We can easily install agent and lib injection software from agent installation script. Given a  sample application we  can enable tracing using local environment variables.  
        Assertions in this tests: 
        - After starting application we can see application HTTP requests traces in the backend.
        - Using the agent installation script we can install different versions of the software (release or beta) in different OS.'''
        
    print(f"Launching test for : [{ip}]")
    print(f"Waiting for weblog available [{ip}]")
    wait_for_port(5985, ip, 60.0)
    print(f"[{ip}]: Weblog app is ready!")
    print(f"Making a request to weblog [{ip}]")
    request_uuid = make_get_request("http://" + ip + ":5985/")
    print(f"Http request done with uuid: [{request_uuid}] for ip [{ip}]")
    wait_backend_trace_id(request_uuid, 120.0)
