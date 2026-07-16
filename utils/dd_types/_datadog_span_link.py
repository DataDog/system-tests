_LEN_TRACE_ID_PARTS = 16


class DataDogSpanLink:
    # The Datadog specific tracecontext flags to mark flags are set
    TRACECONTEXT_FLAGS_SET = 1 << 31

    def __init__(self, data: dict, trace_id: str, trace_id_low: int, trace_id_high: int):
        self.data = data
        self.trace_id = trace_id
        self.trace_id_low = trace_id_low
        self.trace_id_high = trace_id_high

        self.attributes: dict[str, str] | None = data.get("attributes")
        self.trace_state: str | None = data.get("tracestate", data.get("trace_state"))
        self.flags: int = (data["flags"] | self.TRACECONTEXT_FLAGS_SET) if "flags" in data else 0

        if "span_id" in self.data:
            self.span_id = data["span_id"] if isinstance(data["span_id"], int) else int(data["span_id"], base=16)
        elif "spanID" in self.data:  # spanID is a string on base 10
            self.span_id = int(data["spanID"])
        else:
            raise ValueError(f"No span id exists in span link: {data}")

    @staticmethod
    def from_span_links(data: dict) -> "DataDogSpanLink":
        return DataDogSpanLink(
            data, trace_id=data["traceID"], trace_id_high=int(data["traceIDHigh"]), trace_id_low=int(data["traceID"])
        )

    @staticmethod
    def from_efficient_trace_payload_format(data: dict) -> "DataDogSpanLink":
        trace_id = data["traceID"]

        return DataDogSpanLink(
            data,
            trace_id=trace_id,
            trace_id_high=(int(trace_id, 16) >> 64) & 0xFFFFFFFFFFFFFFFF,
            trace_id_low=int(trace_id, 16) & 0xFFFFFFFFFFFFFFFF,
        )

    @staticmethod
    def from_library_v1_span_links(data: dict) -> "DataDogSpanLink":
        # trace Id can be Go-style (int) and Java-style (hex string e.g. '0x...'). Encode int into java style
        trace_id: str = hex(data["trace_id"]) if isinstance(data["trace_id"], int) else data["trace_id"]

        if "trace_id_high" not in data:
            assert trace_id.startswith("0x")
            assert len(trace_id) > _LEN_TRACE_ID_PARTS + 2
            # 128-bit: high 64 bits (first 16 hex chars after 0x)
            trace_id_high = int(trace_id[2 : _LEN_TRACE_ID_PARTS + 2], base=16)
        else:
            trace_id_high = data["trace_id_high"]

        return DataDogSpanLink(
            data,
            trace_id=trace_id,
            trace_id_high=trace_id_high,
            trace_id_low=int(trace_id, 16) & 0xFFFFFFFFFFFFFFFF,
        )

    @staticmethod
    def from_library_v1_attributes(data: dict) -> "DataDogSpanLink":
        trace_id = data["trace_id"]
        assert isinstance(trace_id, str)

        if "trace_id_high" not in data:
            assert trace_id.startswith("0x")
            assert len(trace_id) > _LEN_TRACE_ID_PARTS + 2
            trace_id_high = int(trace_id[2:18], base=16)  # 128-bit: high 64 bits (first 16 hex chars after 0x)
        else:
            trace_id_high = data["trace_id_high"]

        return DataDogSpanLink(
            data,
            trace_id=trace_id,
            trace_id_high=trace_id_high,
            trace_id_low=int(trace_id, 16) & 0xFFFFFFFFFFFFFFFF,
        )

    @staticmethod
    def from_legacy_format(data: dict) -> "DataDogSpanLink":
        trace_id = data["trace_id"]

        return DataDogSpanLink(
            data,
            trace_id=trace_id,
            trace_id_high=int(trace_id[:_LEN_TRACE_ID_PARTS], base=16),
            trace_id_low=int(trace_id[-_LEN_TRACE_ID_PARTS:], base=16),
        )

    @staticmethod
    def from_library_legacy_format(data: dict) -> "DataDogSpanLink":
        # trace Id can be Go-style (int) and Java-style (hex string e.g. '0x...'). Encode int into java style
        trace_id: str = hex(data["trace_id"]) if isinstance(data["trace_id"], int) else data["trace_id"]

        return DataDogSpanLink(
            data,
            trace_id=trace_id,
            trace_id_high=int(trace_id[:_LEN_TRACE_ID_PARTS], base=16) if len(trace_id) > _LEN_TRACE_ID_PARTS else 0,
            trace_id_low=int(trace_id[-_LEN_TRACE_ID_PARTS:], base=16),
        )

    def __str__(self) -> str:
        return str(self.data)

    def __repr__(self) -> str:
        return repr(self.data)
