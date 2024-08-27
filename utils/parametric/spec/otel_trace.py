from typing import TypedDict
from utils.parametric.protos import apm_test_client_pb2 as pb

OTEL_UNSET_CODE = "UNSET"
OTEL_ERROR_CODE = "ERROR"
OTEL_OK_CODE = "OK"

SK_UNSPECIFIED = 0
SK_INTERNAL = 1
SK_SERVER = 2
SK_CLIENT = 3
SK_PRODUCER = 4
SK_CONSUMER = 5


class OtelSpanContext(TypedDict):
    trace_id: str
    span_id: str
    trace_flags: str
    trace_state: str
    remote: bool


def check_list_type(value, t: type) -> bool:
    if value and all(isinstance(item, t) for item in value):
        return True
    return False


# values for otel span attributes can be a list -
# to avoid having multiple map fields in Attributes
# (one where the value is type ListVal, another where value is type AttrVal)
# we just represent all values in List form
def get_val(v) -> pb.ListVal:
    if isinstance(v, list) and check_list_type(v, str):
        return pb.ListVal(val=[pb.AttrVal(string_val=i) for i in v])
    if isinstance(v, list) and check_list_type(v, bool):
        return pb.ListVal(val=[pb.AttrVal(bool_val=i) for i in v])
    if isinstance(v, list) and check_list_type(v, float):
        return pb.ListVal(val=[pb.AttrVal(double_val=i) for i in v])
    if isinstance(v, list) and check_list_type(v, int):
        return pb.ListVal(val=[pb.AttrVal(integer_val=i) for i in v])
    if isinstance(v, str):
        return pb.ListVal(val=[pb.AttrVal(string_val=v)])
    if isinstance(v, bool):
        return pb.ListVal(val=[pb.AttrVal(bool_val=v)])
    if isinstance(v, float):
        return pb.ListVal(val=[pb.AttrVal(double_val=v)])
    if isinstance(v, int):
        return pb.ListVal(val=[pb.AttrVal(integer_val=v)])
    return None


# converts a dictionary containing span attributes into
# the proto message "Attributes"
def convert_to_proto(attributes: dict) -> pb.Attributes:
    list_attr = {}
    if not attributes:
        return pb.Attributes()
    for k, v in attributes.items():
        ret = get_val(v)
        if ret:
            list_attr[k] = ret
    return pb.Attributes(key_vals=list_attr)
