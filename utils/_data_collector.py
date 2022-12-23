# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import collections
from os import listdir
from os.path import isfile, join
import threading
import time

from utils.tools import logger


def get_files(path):
    return [join(path, f) for f in listdir(path) if isfile(join(path, f))]


class _DataCollector(threading.Thread):
    """
    The purpose of this class is spy logs/interfaces folder and call a callback when
    a new file is available
    """

    def __init__(self):
        threading.Thread.__init__(self)

        self.running = False
        self.proxy_callbacks = collections.defaultdict(list)
        self.known_files = {
            "agent": set(),
            "library": set(),
        }

    def new_file(self, interface, file):
        for callback in self.proxy_callbacks[interface]:
            try:
                callback(file)
            except Exception:
                logger.exception("Fail to ...")

    def run(self):
        self.running = True
        logger.info("Data collector is running")

        while self.running:
            for interface, known_files in self.known_files.items():
                files = get_files(f"logs/interfaces/{interface}")
                for file in files:
                    if file not in known_files:
                        known_files.add(file)
                        self.new_file(interface, file)

            time.sleep(0.25)

        logger.info("Data collector is stopped")

    # Main thread domain
    def shutdown(self):
        logger.info("Send stop signal to data collector")
        self.running = False


# singleton
data_collector = _DataCollector()

if __name__ == "__main__":
    data_collector.run()
