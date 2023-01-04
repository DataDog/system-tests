# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import threading
import logging
import collections
import traceback

from werkzeug.serving import make_server
from flask import Flask, request
from utils.tools import logger


class _DataCollector(threading.Thread):
    """
    The purpose of this class is to expose an HTTP entry point that collects
    data from components, and route them to corresponding interface validators
    """

    def __init__(self):
        threading.Thread.__init__(self)

        self.server = None
        self.validated_rule_names = set()
        self.proxy_callbacks = collections.defaultdict(list)

        # monkey patch click (clean output)
        import click

        click.echo = lambda *args, **kwargs: None
        click.secho = lambda *args, **kwargs: None

        app = Flask(__name__)
        self.app = app

        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        app.logger.setLevel(logging.ERROR)

        @app.route("/health", methods=["GET"])
        def health():
            return "Ok"

        @app.route("/proxy/<interface>", methods=["POST", "GET"])
        def messages_from_proxy(interface):
            assert interface in ("agent", "library")

            data = request.get_json()

            for callback in self.proxy_callbacks[interface]:
                try:
                    callback(data)
                except Exception as e:
                    msg = traceback.format_exception_only(type(e), e)[0]
                    logger.critical(msg)

            return "Ok"

    def __str__(self):
        return f"{self.__class__.__name__}()"

    def __repr__(self):
        return f"{self.__class__.__name__}()"

    def run(self):
        logger.info("runner is listening to port 8081")
        self.server = make_server("0.0.0.0", 8081, self.app)
        context = self.app.app_context()
        context.push()

        self.server.serve_forever()

    # Main thread domain
    def shutdown(self):
        self.server.shutdown()


# singleton
data_collector = _DataCollector()

if __name__ == "__main__":
    data_collector.run()
