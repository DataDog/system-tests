import json
import os
from scenarios.fuzzer.tools._tools import cached_property


class _Data(object):
    def __init__(self):

        self.header_valid_list = "!#$%&'*+-.0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ^_`abcdefghijklmnopqrstuvwxyz|~"

    @cached_property
    def _data_path(self):
        return os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

    @cached_property
    def blns(self):
        return json.load(open(os.path.join(self._data_path, "blns.json"), "r"))

    @cached_property
    def re2_regexs(self):
        return [item["Pattern"] for item in self.re2_regexs_with_metadata]

    @cached_property
    def re2_regexs_with_metadata(self):
        return json.load(open(os.path.join(self._data_path, "regex.json"), "r"))
