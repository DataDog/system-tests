# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import json
import random

from tests.fuzzer.html_parser import extract_requests


class RequestGenerator:
    corpus_max_size = 10000  # How many valid requests do we save ?
    corpus_request_max_size = 10000  # do not save valid requests bigger than this

    def __init__(self, mutator, corpus):
        super().__init__()

        # mutation engine
        self.mutator = mutator

        # list of interesting request to be mutated
        self.corpus = []

        # list of request to be sent in priority
        # initialize it with initial corpus
        self.buffer = []
        for request in corpus:
            self.mutator.clean_request(request)
            self.buffer.append(request)

        self.not_found_response_is_parsed = False
        self.parsed = set()

    def add_in_buffer(self, request) -> None:
        if not request.get("path", None):
            return

        self.buffer.append(request)

    def add_in_corpus(self, request) -> None:
        if not request.get("path", None):
            return

        request["method"] = request["method"].upper()

        request_as_json = json.dumps(request)

        if len(request_as_json) < self.corpus_request_max_size and request_as_json not in self.corpus:
            self.corpus.append(request_as_json)

        while len(self.corpus) > self.corpus_max_size:
            self.corpus.pop(0)

    def get_request(self) -> dict:
        if len(self.buffer) != 0:
            request = self.buffer.pop(0)
        else:
            if len(self.corpus) == 0:
                request = {"method": "GET", "path": "/"}
            else:
                request = json.loads(random.choice(self.corpus))

            self.mutator.mutate(request)

        return request

    #############################
    async def feedback(self, request, response, base_url) -> None:
        endpoint = request["method"], request["path"]

        if response.status == 404 and not self.not_found_response_is_parsed:
            self.not_found_response_is_parsed = True
            text = await response.text()
            extract_requests(text, base_url, self.add_in_buffer)

        elif response.status == 403:
            self.add_in_corpus(request)

        elif response.status == 200:
            self.add_in_corpus(request)

            if len(self.parsed) < 10000 and endpoint not in self.parsed:
                self.parsed.add(endpoint)
                text = await response.text()

                extract_requests(text, base_url, self.add_in_buffer)

    def __str__(self):
        return f"<{self.__class__.__name__}> with {self.mutator} mutator"

    def __iter__(self):
        request = self.get_request()
        while request is not None:
            yield request
            request = self.get_request()
