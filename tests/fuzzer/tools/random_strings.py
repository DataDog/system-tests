#!/usr/bin/env python3

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


import random
from tests.fuzzer.tools._tools import cached_property


class _StringLists:
    def __init__(self):
        self.latin1 = ""

        for i in range(0x20, 0x7F):
            self.latin1 += bytes([i]).decode("latin1")

        for i in range(0xA0, 0xFF + 1):
            self.latin1 += bytes([i]).decode("latin1")

    def get_random_unicode(self, min_length=1, max_length=255):
        length = random.randint(min_length, max_length)
        return "".join(random.choices(self.unicode, k=length))

    def get_random_unicode_char(self):
        return random.choice(self.unicode)

    @cached_property
    def unicode(self):
        result = []

        def append(*args: int):
            value = bytes(args).decode()
            result.append(value)

        for i in range(0b01111111 + 1):
            append(i)

        for i in range(0b11000010, 0b11011111 + 1):
            for j in range(0b10000000, 0b10111111 + 1):
                append(i, j)

        # 11100000 101xxxxx 10xxxxxx
        for j in range(0b10100000, 0b10111111 + 1):
            for k in range(0b10000000, 0b10111111 + 1):
                append(0b11100000, j, k)

        # 11100001 10xxxxxx 10xxxxxx
        for j in range(0b10000000, 0b10111111 + 1):
            for k in range(0b10000000, 0b10111111 + 1):
                append(0b11100001, j, k)

        # 1110001x 10xxxxxx 10xxxxxx
        for i in range(0b11100010, 0b11100011 + 1):
            for j in range(0b10000000, 0b10111111 + 1):
                for k in range(0b10000000, 0b10111111 + 1):
                    append(i, j, k)

        # 111001xx 10xxxxxx 10xxxxxx
        for i in range(0b11100100, 0b11100111 + 1):
            for j in range(0b10000000, 0b10111111 + 1):
                for k in range(0b10000000, 0b10111111 + 1):
                    append(i, j, k)

        # 111010xx 10xxxxxx 10xxxxxx
        for i in range(0b11101000, 0b11101011 + 1):
            for j in range(0b10000000, 0b10111111 + 1):
                for k in range(0b10000000, 0b10111111 + 1):
                    append(i, j, k)

        # 11101100 10xxxxxx 10xxxxxx
        for j in range(0b10000000, 0b10111111 + 1):
            for k in range(0b10000000, 0b10111111 + 1):
                append(0b11101100, j, k)

        # 11101101 100xxxxx 10xxxxxx
        for j in range(0b10000000, 0b10011111 + 1):
            for k in range(0b10000000, 0b10111111 + 1):
                append(0b11101101, j, k)

        # 1110111x 10xxxxxx 10xxxxxx
        for i in range(0b11101110, 0b11101111 + 1):
            for j in range(0b10000000, 0b10111111 + 1):
                for k in range(0b10000000, 0b10111111 + 1):
                    append(i, j, k)

        # 11110000 1001xxxx 10xxxxxx 10xxxxxx
        for j in range(0b10010000, 0b10011111 + 1):
            for k in range(0b10000000, 0b10111111 + 1):
                for z in range(0b10000000, 0b10111111 + 1):
                    append(0b11110000, j, k, z)

        # 11110000 101xxxxx 10xxxxxx 10xxxxxx
        for j in range(0b10100000, 0b10111111 + 1):
            for k in range(0b10000000, 0b10111111 + 1):
                for z in range(0b10000000, 0b10111111 + 1):
                    append(0b11110000, j, k, z)

        # 11110001 10xxxxxx 10xxxxxx 10xxxxxx
        for j in range(0b10000000, 0b10111111 + 1):
            for k in range(0b10000000, 0b10111111 + 1):
                for z in range(0b10000000, 0b10111111 + 1):
                    append(0b11110001, j, k, z)

        # 1111001x 10xxxxxx 10xxxxxx 10xxxxxx
        for i in range(0b11110010, 0b11110011 + 1):
            for j in range(0b10000000, 0b10111111 + 1):
                for k in range(0b10000000, 0b10111111 + 1):
                    for z in range(0b10000000, 0b10111111 + 1):
                        append(i, j, k, z)

        # 11110100 1000xxxx 10xxxxxx 10xxxxxx
        for j in range(0b10000000, 0b10001111 + 1):
            for k in range(0b10000000, 0b10111111 + 1):
                for z in range(0b10000000, 0b10111111 + 1):
                    append(0b11110100, j, k, z)

        return result


string_lists = _StringLists()
get_random_unicode = string_lists.get_random_unicode
get_random_unicode_char = string_lists.get_random_unicode_char


def get_random_latin1(min_length=0, max_length=255) -> str:
    length = random.randint(min_length, max_length)
    return "".join(random.choices(string_lists.latin1, k=length))


def get_random_string(population: list[str], min_length: int = 0, max_length: int = 255) -> str:
    length = random.randint(min_length, max_length)
    return "".join(random.choices(population, k=length))
