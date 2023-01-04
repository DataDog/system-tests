from datetime import datetime
import json
from os import environ
import time
import threading

import requests
import docker


MAX_CONCURRENT_REQUEST = 5
TOTAL_REQUEST_COUNT = 10000
WARMUP_REQUEST_COUNT = 10
WARMUP_LAST_SLEEP_DURATION = 3

WEBLOG_URL = environ["WEBLOG_URL"] if "WEBLOG_URL" in environ else "http://weblog:7777"
LOG_FOLDER = environ["LOG_FOLDER"] if "LOG_FOLDER" in environ else "/app/logs"
TESTED_PATHS = ("/", "/waf/", "/waf/fdsfds/fds/fds/fds/", "/waf?a=b", "/waf?acd=bcd", "/waf?a=b&a=c")

# TOTAL_REQUEST_COUNT = 100
# WARMUP_REQUEST_COUNT = 1
# WARMUP_LAST_SLEEP_DURATION = 1
# WEBLOG_URL="http://localhost:7777"
# LOG_FOLDER="logs"
class Runner:
    def __init__(self) -> None:
        self.requests = []
        self.build_requests()

        self.results = []
        self.memory = []
        self.finished = False

    def build_requests(self):
        headers = (None, {"User-Agent": "normal"}, {"x-filename": "test"})

        datas = ({"a": "value"}, {"b": "other value", "bypass": "normal"})

        def nested(size, deep):
            if deep < 0:
                return "xxx"
            return {f"k{i}": nested(size, deep - 1) for i in range(size)}

        medium_nested = nested(5, 5)
        big_nested = nested(6, 6)

        for _ in range(5):
            for path in TESTED_PATHS:
                for header in headers:
                    self.add_request({"method": "GET", "url": f"{WEBLOG_URL}{path}", "headers": header})

            for path in TESTED_PATHS:
                for header in headers:
                    for data in datas:
                        self.add_request(
                            {"method": "POST", "url": f"{WEBLOG_URL}{path}", "headers": header, "data": data}
                        )

        for path in TESTED_PATHS:
            for header in headers:
                for data in datas:
                    for _ in range(5):
                        self.add_request(
                            {"method": "POST", "url": f"{WEBLOG_URL}{path}", "headers": header, "json": medium_nested,}
                        )

                    self.add_request(
                        {"method": "POST", "url": f"{WEBLOG_URL}{path}", "headers": header, "json": big_nested}
                    )

    def add_request(self, request):
        if "headers" in request and request["headers"] is None:
            del request["headers"]
        size = len(str([request.values()]))
        self.requests.append((size, request))

    def run(self):
        appsec = "with_appsec" if environ["DD_APPSEC_ENABLED"] == "true" else "without_appsec"
        lang = environ["SYSTEM_TESTS_LIBRARY"]

        print(f"Testing {lang} {appsec}")
        print("Warmup...", flush=True)

        # warmup
        for _ in range(WARMUP_REQUEST_COUNT):
            requests.get(WEBLOG_URL, timeout=10)
            time.sleep(0.6)

        time.sleep(WARMUP_LAST_SLEEP_DURATION)
        print("Warmup ok", flush=True)

        threads = [threading.Thread(target=self.watch_docker_target)] + [
            threading.Thread(target=self.fetch) for _ in range(MAX_CONCURRENT_REQUEST)
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        data = {"durations": self.results, "memory": self.memory}

        with open(f"{LOG_FOLDER}/stats_{lang}_{appsec}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def fetch(self):
        i = 0
        while len(self.results) < TOTAL_REQUEST_COUNT:
            if len(self.results) % 100 == 0:
                print(f"{len(self.results)} / {TOTAL_REQUEST_COUNT}", flush=True)
            i += 1
            try:
                size, request = self.requests[i % len(self.requests)]

                request_timestamp = datetime.now()
                r = requests.request(**request)
                ellapsed = (datetime.now() - request_timestamp).total_seconds()

                self.results.append((i, ellapsed, r.status_code, size))
            except Exception as e:
                print(e)
                raise

    def watch_docker_target(self):
        start = datetime.now()
        docker_client = docker.from_env()
        container_stats = docker_client.containers.get("/system-tests_runner_1").stats(decode=True)

        while len(self.results) < TOTAL_REQUEST_COUNT:
            data = next(container_stats)
            memory = data["memory_stats"].get("usage", 0)
            self.memory.append(((datetime.now() - start).total_seconds(), memory))

            print("MEM", datetime.now(), memory, flush=True)


Runner().run()
