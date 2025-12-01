# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import random
import argparse

from utils._context.containers import WeblogContainer, AgentContainer, create_network
from utils._logger import get_logger
from utils import context, scenarios
from tests.fuzzer.core import Fuzzer


def main() -> None:
    context.scenario = scenarios.fuzzer

    parser = argparse.ArgumentParser(description="Send a bunch of requests to an url.")

    parser.add_argument("corpus", nargs="?", type=str, help="Base corpus", default="tests/fuzzer/corpus")

    parser.add_argument(
        "--concurrent",
        "-c",
        type=int,
        help="How many concurrent requests run",
        default=8,
    )
    parser.add_argument(
        "--dump",
        "-d",
        type=str,
        help="Save request with this HTTP status",
        default="500,501",
    )
    parser.add_argument("--export", "-e", help="Export all requests in a dump", action="store_true")
    parser.add_argument(
        "--report_frequency",
        "-f",
        type=int,
        help="Report frequency (default 1s)",
        default=1,
    )
    parser.add_argument("--request_count", "-n", type=int, help="How many request to send", default=None)
    parser.add_argument("--port", "-p", type=str, help="Port to request", default="7777")
    parser.add_argument("--seed", "-s", type=str, help="seed for random", default=None)
    parser.add_argument("--max_time", "-t", type=int, help="Max time in seconds", default=None)
    parser.add_argument("--url", "-u", type=str, help="URL to request", default="http://localhost")
    parser.add_argument("--debug", help="Enable asyncio debug mode", action="store_true")
    parser.add_argument("--no-mutation", help="disable mutation", action="store_true")
    parser.add_argument("--slack_channel", help="Set slack channel", default=None)
    parser.add_argument("--slack_token", help="Set slack token", default=None)

    args = parser.parse_args()

    assert args.url.startswith("http"), "url argument must starts with http"

    if args.seed is None:
        args.seed = "".join(random.choices("1234567890abcdef", k=8))

    logger = get_logger(use_stdout=True)

    network = create_network()

    agent = AgentContainer(use_proxy=False)
    agent.configure(host_log_folder="logs_fuzzer", replay=False)
    agent.start(network)

    weblog = WeblogContainer(use_proxy=False)
    weblog.configure(host_log_folder="logs_fuzzer", replay=False)
    weblog.start(network)
    weblog.post_start()

    Fuzzer(
        corpus=args.corpus,
        no_mutation=args.no_mutation,
        base_url=f"{args.url}:{args.port}",
        seed=args.seed,
        report_frequency=args.report_frequency,
        max_tasks=args.concurrent,
        max_time=args.max_time,
        dump_on_status=args.dump.split(","),
        systematic_export=args.export,
        debug=args.debug,
        request_count=args.request_count,
        logger=logger,
        weblog=weblog,
    ).run_forever()


main()
