import requests
from random import randint

def make_get_request(app_url):
    generated_uuid=str( randint(0, 10000000))
    requests.get(app_url, headers={"x-datadog-trace-id":generated_uuid})
    return generated_uuid