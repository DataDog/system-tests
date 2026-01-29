# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from google.protobuf.descriptor_pb2 import FileDescriptorSet
from google.protobuf.message_factory import GetMessages
from google.protobuf import message

from pathlib import Path


def _get_mesages(filename: str) -> dict[str, type[message.Message]]:
    with open(Path(__file__).parent / filename, "rb") as f:
        _fds = FileDescriptorSet.FromString(f.read())

    return GetMessages(list(_fds.file))


_messages = _get_mesages("agent.descriptor")
TracePayload = _messages["datadog.trace.AgentPayload"]
MetricPayload = _messages["datadog.agentpayload.MetricPayload"]
SketchPayload = _messages["datadog.agentpayload.SketchPayload"]

_backend_messages = _get_mesages("backend.descriptor")
BackendResponsePayload = _backend_messages["datadoghq.api.series.v2.Response"]

_remoteconfig_messages = _get_mesages("remoteconfig.descriptor")
LatestConfigsResponse = _remoteconfig_messages["datadog.config.LatestConfigsResponse"]
ConfigMetas = _remoteconfig_messages["datadog.config.ConfigMetas"]
DirectorMetas = _remoteconfig_messages["datadog.config.DirectorMetas"]
TopMeta = _remoteconfig_messages["datadog.config.TopMeta"]
File = _remoteconfig_messages["datadog.config.File"]
OrgDataResponse = _remoteconfig_messages["datadog.config.OrgDataResponse"]
OrgStatusResponse = _remoteconfig_messages["datadog.config.OrgStatusResponse"]
