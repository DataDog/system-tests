from enum import IntEnum


class ProxyPorts(IntEnum):
    """Proxy port are used by the proxy to determine the provenance of the request"""

    proxy_commands = 11111

    weblog = 8126
    open_telemetry_weblog = 8127
    otel_collector = 8128

    agent = 8200

    python_buddy = 9001
    nodejs_buddy = 9002
    java_buddy = 9003
    ruby_buddy = 9004
    golang_buddy = 9005
