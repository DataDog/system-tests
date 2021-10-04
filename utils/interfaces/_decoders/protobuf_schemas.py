from google.protobuf.descriptor_pb2 import FileDescriptorSet
from google.protobuf.message_factory import GetMessages

from pathlib import Path


def _get_schema(descriptor_name, name):
    with open(Path(__file__).parent / descriptor_name, "rb") as f:
        fds = FileDescriptorSet.FromString(f.read())
    messages = GetMessages([file for file in fds.file])
    return messages[name]


TracePayload = _get_schema("trace_payload.descriptor", "pb.TracePayload")
