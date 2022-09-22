import requests


class _ProxyState:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def set_state(self, key, value):
        assert value in (True, False)

        r = requests.get(f"http://{self.host}:{self.port}/_system_tests_state")
        state = r.json()
        state[key] = value
        state = requests.post(f"http://{self.host}:{self.port}/_system_tests_state", json=state)

        return state


class _Proxies:
    agent = _ProxyState("agent_proxy", 8082)
    library = _ProxyState("library_proxy", 8126)


proxies = _Proxies()
