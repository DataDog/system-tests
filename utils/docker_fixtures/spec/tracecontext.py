# Copyright (c) 2018 W3C and contributors

# Redistribution and use in source and binary forms, with or without modification, are permitted provided that
# the following conditions are met:

# 1. Redistributions of works must retain the original copyright notice, this list of conditions and the
#    following disclaimer.
# 2. Redistributions in binary form must reproduce the original copyright notice, this list of conditions and the
#    following disclaimer in the documentation and/or other materials provided with the distribution.
# 3. Neither the name of the W3C nor the names of its contributors may be used to endorse or promote products derived
#    from this work without specific prior written permission.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


from collections import OrderedDict
import re

# The Datadog specific tracecontext flags to mark flags are set
TRACECONTEXT_FLAGS_SET = 1 << 31

traceparent_name_re = re.compile(r"^traceparent$", re.IGNORECASE)
tracestate_name_re = re.compile(r"^tracestate$", re.IGNORECASE)


def get_tracecontext(headers: dict[str, str]) -> tuple:
    return get_traceparent(headers), get_tracestate(headers)


class Traceparent:
    def __init__(
        self,
        version: int | str = 0,
        trace_id: int | str | None = None,
        parent_id: int | str | None = None,
        trace_flags: int | str = 0,
    ):
        self.version = version
        self.trace_id = trace_id
        self.parent_id = parent_id
        self.trace_flags = trace_flags

    def __str__(self) -> str:
        return f"{self.version}-{self.trace_id}-{self.parent_id}-{self.trace_flags}"


# The tracestate class was obtained from:
# https://github.com/w3c/trace-context/blob/84b583d86ecb7005a9eab8fed86ab7117b050b48/test/tracecontext/tracestate.py
# All tests in this Repository are licensed by contributors to be distributed under the W3C 3-clause BSD License:
# https://www.w3.org/Consortium/Legal/2008/03-bsd-license.html
class Tracestate:
    _KEY_WITHOUT_VENDOR_FORMAT = r"[a-z][_0-9a-z\-\*\/]{0,255}"
    _KEY_WITH_VENDOR_FORMAT = r"[0-9a-z][_0-9a-z\-\*\/]{0,240}@[a-z][_0-9a-z\-\*\/]{0,13}"
    _KEY_FORMAT = _KEY_WITHOUT_VENDOR_FORMAT + "|" + _KEY_WITH_VENDOR_FORMAT
    _VALUE_FORMAT = r"[\x20-\x2b\x2d-\x3c\x3e-\x7e]{0,255}[\x21-\x2b\x2d-\x3c\x3e-\x7e]"
    _DELIMITER_FORMAT_RE = re.compile("[ \t]*,[ \t]*")
    _KEY_VALIDATION_RE = re.compile("^(" + _KEY_FORMAT + ")$")
    _VALUE_VALIDATION_RE = re.compile("^(" + _VALUE_FORMAT + ")$")
    _MEMBER_FORMAT_RE = re.compile(f"^({_KEY_FORMAT})(=)({_VALUE_FORMAT})$")

    def __init__(self, *args, **kwds: str):  # noqa: ANN002
        if len(args) == 1 and not kwds:
            if isinstance(args[0], str):
                self._traits: OrderedDict = OrderedDict()
                self.from_string(args[0])
                return
            if isinstance(args[0], Tracestate):
                self._traits = OrderedDict(args[0]._traits)  # noqa: SLF001
                return
        self._traits = OrderedDict(*args, **kwds)

    def __contains__(self, key: str):
        return key in self._traits

    def __len__(self):
        return len(self._traits)

    def __repr__(self):
        return f"{type(self).__name__}({self})"

    def __getitem__(self, key: str):
        return self._traits[key]

    def __setitem__(self, key: str, value: str):
        if not isinstance(key, str):
            raise TypeError("key must be an instance of str")
        if not re.match(self._KEY_VALIDATION_RE, key):
            raise ValueError("illegal key provided")
        if not isinstance(value, str):
            raise TypeError("value must be an instance of str")
        if not re.match(self._VALUE_VALIDATION_RE, value):
            raise ValueError("illegal value provided")
        self._traits[key] = value
        self._traits.move_to_end(key, last=False)

    def __str__(self):
        return self.to_string()

    def from_string(self, string: str) -> "Tracestate":
        for member in re.split(self._DELIMITER_FORMAT_RE, string):
            if member:
                match = self._MEMBER_FORMAT_RE.match(member)
                if not match:
                    raise ValueError(f"illegal key-value format {member}")
                key, _, value = match.groups()
                if key not in self._traits:
                    self._traits[key] = value
                    # If key is already in self._traits, the incoming tracestate header contained a duplicated key.
                    # According to the spec, two behaviors are valid: Either pass on the duplicated key as-is or drop
                    # it. We opt for dropping it.
        return self

    def to_string(self) -> str:
        return ",".join(key + "=" + self[key] for key in self._traits)

    def split(self, char: str = ",") -> list[str]:
        ts = self.to_string()
        return ts.split(char)

    # make this an optional choice instead of enforcement during put/update
    # if the tracestate value size is bigger than 512 characters, the tracer
    # CAN decide to forward the tracestate
    def is_valid(self) -> bool:
        if len(self) == 0:
            return False
        # combined header length MUST be less than or equal to 512 bytes
        if len(self.to_string()) > 512:  # noqa: PLR2004
            return False
        # there can be a maximum of 32 list-members in a list
        return not len(self) > 32  # noqa: PLR2004

    def pop(self) -> tuple[str, str]:
        return self._traits.popitem()


def get_traceparent(headers: dict[str, str]) -> Traceparent | None:
    retval = []
    for key, value in headers.items():
        if traceparent_name_re.match(key):
            retval.append((key, value))

    assert len(retval) == 1
    version, trace_id, span_id, trace_flags = retval[0][1].split("-")

    if len(version) != 2 or len(trace_id) != 32 or len(span_id) != 16 or len(trace_flags) != 2:  # noqa: PLR2004
        return None

    if int(trace_id, 16) == 0 or int(span_id, 16) == 0:
        return None

    return Traceparent(version, trace_id, span_id, trace_flags)


def get_tracestate(headers: dict[str, str]) -> Tracestate:
    tracestate = Tracestate()
    for key, value in headers.items():
        if tracestate_name_re.match(key):
            tracestate.from_string(value)
    return tracestate
