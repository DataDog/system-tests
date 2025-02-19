# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from google.protobuf.descriptor_pb2 import FileDescriptorSet
from google.protobuf.message_factory import GetMessages

from pathlib import Path


with open(Path(__file__).parent / "agent.descriptor", "rb") as f:
    _fds = FileDescriptorSet.FromString(f.read())
_messages = GetMessages(list(_fds.file))

print(f"Message types present in protobuf descriptors: {_messages.keys()}")  # noqa: T201

TracePayload = _messages["datadog.trace.AgentPayload"]
MetricPayload = _messages["datadog.agentpayload.MetricPayload"]
SketchPayload = _messages["datadog.agentpayload.SketchPayload"]
