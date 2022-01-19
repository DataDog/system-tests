import json
from aiohttp import ClientTimeout, ClientSession, UnixConnector, client_exceptions
import asyncio
from datetime import datetime
from os import environ
import time
import requests

MAX_CONCURRENT_REQUEST = 5
TOTAL_REQUEST_COUNT = 10000

WEBLOG_URL="http://weblog:7777"
class Runner:
    def __init__(self) -> None:

        self.loop = asyncio.get_event_loop()
        asyncio.set_event_loop(self.loop)

        self.timeout = ClientTimeout(total=None, sock_connect=10, sock_read=10)

        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUEST)

        self.requests = []
        self.build_requests()

        self.i = 0
        self.results = []

    def build_requests(self):
        paths = ("/", "/waf/", "/waf/fdsfds/fds/fds/fds/")
        headers = (None, [["User-Agent", "normal"]], {"x-filename": "test"})

        datas = ({"a": "value"}, {"b": "other value", "bypass": "normal"})

        def nested(size, deep):
            if deep < 0:
                return "xxx"
            return {f"k{i}": nested(size, deep - 1) for i in range(size)}

        medium_nested = nested(5, 5)
        big_nested = nested(6, 6)

        for _ in range(10):
            for path in paths:
                for header in headers:
                    self.add_request({"method": "GET", "url": f"{WEBLOG_URL}{path}", "headers": header})

            for path in paths:
                for header in headers:
                    for data in datas:
                        self.add_request(
                            {"method": "POST", "url": f"{WEBLOG_URL}{path}", "headers": header, "data": data}
                        )

        for path in paths:
            for header in headers:
                for data in datas:
                    for _ in range(10):
                        self.add_request(
                            {
                                "method": "POST",
                                "url": f"{WEBLOG_URL}{path}",
                                "headers": header,
                                "json": medium_nested,
                            }
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
        print("Warmup", end="")
        # warmup
        for _ in range(10):
            requests.get(WEBLOG_URL)
            print(".", end="", flush=True)
            time.sleep(1)

        print()
        task = asyncio.ensure_future(self._main())
        self.loop.run_until_complete(task)

        json.dump(self.results, open(f"/app/logs/stats_{lang}_{appsec}.json", "w"), indent=2)

    async def fetch(self, session):
        await self.semaphore.acquire()

        self.i += 1
        i = self.i

        try:

            request_timestamp = datetime.now()
            size, request = self.requests[i % len(self.requests)]
            async with session.request(ssl=False, timeout=self.timeout, **request) as response:
                status = response.status
                # content = await response.read()
                ellapsed = (datetime.now() - request_timestamp).total_seconds()
                self.results.append((i, ellapsed, status, size))
                return "OK"
        except Exception as e:
            print("ERROR", str(e))
        finally:
            self.semaphore.release()

    async def _main(self):

        tasks = []

        async with ClientSession() as session:
            for _ in range(TOTAL_REQUEST_COUNT):
                tasks.append(asyncio.ensure_future(self.fetch(session)))

            responses = asyncio.gather(*tasks)
            await responses

        return responses

    async def watch_docker_target(self):
        try:
            session = ClientSession(loop=self.loop, connector=UnixConnector(path="/var/run/docker.sock"))

            async with session.get("http://localhost/containers/systemtests_weblog_1/stats") as resp:
                async for line in resp.content:
                    data = json.loads(line)
                    print(data["memory_stats"]["usage"])

        except FileNotFoundError:
            print("Docker socket not found")
        except client_exceptions.ClientConnectorError:
            print("Can't connect to Docker socket")
        except Exception as e:
            print(f"Unexpected exception when connecting to Docker socket: {e}")

        finally:
            if session:
                await session.close()


Runner().run()
