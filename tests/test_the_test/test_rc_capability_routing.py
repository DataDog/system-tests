"""Validate the capability-routing fixture independently of SDK/Agent behavior."""

import base64
import json

import requests
from google.protobuf.json_format import ParseDict
from utils import pytest, scenarios
from utils.mocked_backend import MockedBackendServer
from utils.mocked_backend.rc_capabilities import BASE_PATH, DEPENDENT_PATH
from utils.proxy._decoders.protobuf_schemas import LatestConfigsRequest, LatestConfigsResponse


def client(client_id: str, *bits: int) -> dict:
    return {
        "id": client_id,
        "products": ["FFE_FLAGS"],
        "capabilities": base64.b64encode(sum(1 << bit for bit in bits).to_bytes(7, "big")).decode(),
    }


@scenarios.test_the_test
@pytest.mark.parametrize("preloaded", [False, True])
def test_rc_routing_changes_without_republishing(*, preloaded: bool) -> None:
    server = MockedBackendServer()
    try:
        publication = server.client.rc_publish_capability_variants({"flags": {}}, {"flags": {"child": {}}})
        with pytest.raises(requests.HTTPError, match="409"):
            server.client.rc_publish_capability_variants({"flags": {}}, {"flags": {}})

        def poll(clients: list[dict]) -> dict:
            # Exercise the actual protobuf request decoder and HTTP route, including signed capabilities.
            request = ParseDict({"active_clients": clients}, LatestConfigsRequest())
            response = requests.post(
                server.base_url + "/api/v0.1/configurations",
                data=request.SerializeToString(),
                headers={"Content-Type": "application/x-protobuf"},
                timeout=5,
            )
            response.raise_for_status()
            parsed = LatestConfigsResponse.FromString(response.content)
            return {
                "director": json.loads(parsed.director_metas.targets.raw),  # type: ignore[attr-defined]
                "config": parsed.config_metas.SerializeToString(),  # type: ignore[attr-defined]
                "files": {file.path: file.raw for file in parsed.target_files},  # type: ignore[attr-defined]
            }

        others = [client("preloaded", 46, 50), client("legacy", 46)] if preloaded else []
        initial = poll([client("java", 46), *others])
        stable = poll([client("java", 46), *others])
        upgraded = poll([client("java", 46, 50), *others])
        assert initial["config"] == stable["config"] == upgraded["config"]
        assert (
            initial["director"]["signed"]["version"]
            < stable["director"]["signed"]["version"]
            < upgraded["director"]["signed"]["version"]
        )
        base = initial["director"]["signed"]["targets"][BASE_PATH]["custom"]
        assert {predicate["clientID"] for predicate in base["tracer-predicates"]["tracer_predicates_v1"]} == {
            "java",
            *(["legacy"] if preloaded else []),
        }
        dependent = upgraded["director"]["signed"]["targets"][DEPENDENT_PATH]["custom"]
        assert {predicate["clientID"] for predicate in dependent["tracer-predicates"]["tracer_predicates_v1"]} == {
            "java",
            *(["preloaded"] if preloaded else []),
        }
        if preloaded:
            assert set(initial["files"]) == set(upgraded["files"]) == {BASE_PATH, DEPENDENT_PATH}
        assert (DEPENDENT_PATH in initial["files"]) == preloaded
        assert initial["files"][BASE_PATH] == stable["files"][BASE_PATH]
        unsupported = poll([client("unsupported", 50)])
        assert unsupported["director"]["signed"]["targets"] == {}
        assert server.client.rc_capability_status()["hashes"] == publication["hashes"]
    finally:
        server.close()
