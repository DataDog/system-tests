import pytest
from weblog_interface import *
from backend_interface import *

# String Concatenate
def test_forTraces():
    request_uuid=make_get_request("http://" + pytest.public_ip + ":7777/")
    print(f"http request done with uuid:",request_uuid)
    wait_backend_trace_id(request_uuid,30.0)