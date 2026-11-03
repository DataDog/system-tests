"""Unit coverage for flag selection on the mocked FFE agentless configuration endpoint."""

from dataclasses import dataclass
import http.client
import json
from pathlib import Path
from urllib.parse import quote, urlsplit

import requests
from utils import pytest

from utils import scenarios
from utils.mocked_backend import MockedBackendServer
from utils.mocked_backend._ffe_flag_selection import (
    SelectionIgnoredError,
    has_selection_parameters,
    parse_selection,
    select_flags,
)
from utils.mocked_backend.ffe import (
    CONFIG_PATH,
    CONFIG_QUERY,
    EVALUATION_SUITES_RELATIVE_PATH,
    FLAG_SELECTION_IGNORED_HEADER,
    UFC_FIXTURE_RELATIVE_PATH,
    Selection,
    ufc_etag_for,
)

REPO_ROOT = Path(__file__).parents[2]
VECTORS = json.loads(
    (REPO_ROOT / "tests/parametric/test_ffe/ffe-system-test-data/flag-selection/selection-vectors.json").read_text()
)
UFC_FLAGS = sorted(json.loads((REPO_ROOT / UFC_FIXTURE_RELATIVE_PATH).read_text())["flags"])
SUITE = "flag-selection"
SUITE_FLAGS = sorted(
    json.loads((REPO_ROOT / EVALUATION_SUITES_RELATIVE_PATH / SUITE / "ufc-config.json").read_text())["flags"]
)
CHECKOUT_FLAGS = ["checkout-banner", "checkout-pricing"]


def _encode(value: str) -> str:
    # Escape every reserved character, so '+', '%', '&', '=' and '*' in a value reach the parser literally.
    return quote(value, safe="-_.~")


def _vector_query(case: dict) -> str:
    if "rawQuery" in case:
        return case["rawQuery"]
    return "&".join(f"{name}={_encode(value)}" for name, values in case["query"].items() for value in values)


@scenarios.test_the_test
@pytest.mark.parametrize("case", VECTORS["cases"], ids=[case["name"] for case in VECTORS["cases"]])
def test_selection_matches_shared_vectors(case: dict) -> None:
    flag_tags = {flag["key"]: flag["tags"] for flag in VECTORS["flags"]}
    raw_query = _vector_query(case)
    expected = case["expected"]

    if expected["outcome"] == "ignored":
        with pytest.raises(SelectionIgnoredError) as error:
            parse_selection(raw_query)
        assert error.value.reason == expected["reason"]
        return

    if not has_selection_parameters(raw_query):
        assert expected["selectedKeys"] == sorted(flag_tags)
        return
    assert select_flags(parse_selection(raw_query), flag_tags) == expected["selectedKeys"]


@dataclass
class _Response:
    status: int
    headers: http.client.HTTPMessage
    body: bytes

    def json(self) -> dict:
        return json.loads(self.body)


def _get(server: MockedBackendServer, query: str, headers: dict[str, str] | None = None) -> _Response:
    # Not requests: it re-encodes invalid percent-escapes such as %zz, which the malformed cases must send as is.
    connection = http.client.HTTPConnection(urlsplit(server.base_url).netloc, timeout=5)
    try:
        connection.request("GET", f"{CONFIG_PATH}?{query}", headers=headers or {})
        response = connection.getresponse()
        return _Response(response.status, response.headers, response.read())
    finally:
        connection.close()


def _get_config(server: MockedBackendServer, selection_query: str = "") -> _Response:
    response = _get(server, f"{CONFIG_QUERY}&{selection_query}" if selection_query else CONFIG_QUERY)
    assert response.status == 200, response.body
    return response


def _flag_keys(response: _Response) -> list[str]:
    return sorted(response.json()["data"]["attributes"]["flags"])


@scenarios.test_the_test
@pytest.mark.parametrize(
    ("selection_query", "expected_keys"),
    [
        ("selected_flag_tags=team%3Acheckout", CHECKOUT_FLAGS),
        ("selected_flag_tags=release%3Asummer%20sale", ["summer-sale"]),
        ("selected_flag_tags=release:summer+sale", ["summer-sale"]),
        ("selected_flag_key_patterns=search-%2A", ["search-ranking"]),
        (
            "selected_flag_tags=team%3Aops&selected_flag_key_patterns=checkout-b%2A",
            ["checkout-banner", "ops-kill-switch"],
        ),
        ("selected_flag_tags=no-flag-has-this-tag", []),
        ("selected_flag_tags=%85", []),
    ],
)
def test_valid_selection_serves_only_selected_flags(selection_query: str, expected_keys: list[str]) -> None:
    server = MockedBackendServer()
    try:
        server.client.ffe_use_suite(SUITE)
        unfiltered = _get_config(server)
        response = _get_config(server, selection_query)

        assert _flag_keys(response) == expected_keys
        assert FLAG_SELECTION_IGNORED_HEADER not in response.headers
        assert response.headers["ETag"] != unfiltered.headers["ETag"]
        assert (
            response.json()["data"]["attributes"]["environment"]
            == unfiltered.json()["data"]["attributes"]["environment"]
        )
        assert server.ffe_get_requests()[-1]["path"].endswith(selection_query)
    finally:
        server.close()


@scenarios.test_the_test
def test_root_configuration_has_no_tags() -> None:
    server = MockedBackendServer()
    try:
        assert _flag_keys(_get_config(server, "selected_flag_tags=team%3Acheckout")) == []
        assert _flag_keys(_get_config(server, "selected_flag_key_patterns=serial-id-%2A")) == [
            "serial-id-basic-flag",
            "serial-id-missing-flag",
            "serial-id-targeting-flag",
            "serial-id-zero-flag",
        ]
    finally:
        server.close()


@scenarios.test_the_test
def test_suite_control_serves_the_suite_configuration() -> None:
    server = MockedBackendServer()
    try:
        server.client.ffe_use_suite(SUITE)
        response = _get_config(server)
        assert _flag_keys(response) == SUITE_FLAGS
        assert response.headers["ETag"] == ufc_etag_for(None, SUITE)

        server.client.ffe_use_suite("dependent-flags")
        assert _flag_keys(_get_config(server, "selected_flag_tags=team%3Acheckout")) == []

        server.client.ffe_use_suite(None)
        response = _get_config(server)
        assert _flag_keys(response) == UFC_FLAGS
        assert response.headers["ETag"] == ufc_etag_for(None)

        server.client.ffe_use_suite(SUITE)
        server.client.ffe_reset()
        assert _flag_keys(_get_config(server)) == UFC_FLAGS
    finally:
        server.close()


@scenarios.test_the_test
def test_suite_control_rejects_unknown_suites() -> None:
    server = MockedBackendServer()
    try:
        for body in (
            {"suite": "missing-suite"},
            {"suite": "../evaluation-suites/flag-selection"},
            {"suite": "Flag-Selection"},
            {"suite": ""},
            {"suite": 1},
            {},
            {"other": None},
        ):
            response = requests.post(f"{server.base_url}/system-tests/ffe/suite", json=body, timeout=5)
            assert response.status_code == 400, body
    finally:
        server.close()


@scenarios.test_the_test
@pytest.mark.parametrize(
    ("selection_query", "reason"),
    [
        ("selected_flag_tags=%zz", "malformed_selection"),
        ("&".join(f"selected_flag_tags=tag-{index}" for index in range(32)), "too_many_values"),
        ("selected_flag_key_patterns=" + "a" * 201, "invalid_key_pattern"),
        ("selected_flag_tags=" + "a" * 201 + "&selected_flag_tags=team%3Acheckout", "invalid_tag"),
    ],
)
def test_invalid_selection_serves_every_flag_with_reason(selection_query: str, reason: str) -> None:
    server = MockedBackendServer()
    try:
        unfiltered = _get_config(server)
        response = _get_config(server, selection_query)

        assert _flag_keys(response) == UFC_FLAGS
        assert response.headers[FLAG_SELECTION_IGNORED_HEADER] == reason
        assert response.headers["ETag"] == unfiltered.headers["ETag"]
    finally:
        server.close()


@scenarios.test_the_test
def test_absent_or_empty_selection_serves_every_flag_without_reason() -> None:
    server = MockedBackendServer()
    try:
        for selection_query in ("", "selected_flag_tags=%20&selected_flag_key_patterns="):
            response = _get_config(server, selection_query)
            assert _flag_keys(response) == UFC_FLAGS, selection_query
            assert FLAG_SELECTION_IGNORED_HEADER not in response.headers, selection_query
    finally:
        server.close()


@scenarios.test_the_test
def test_selection_does_not_relax_the_environment_query() -> None:
    server = MockedBackendServer()
    try:
        for query in (
            "selected_flag_tags=team%3Acheckout",
            "dd_env=test&dd_env=wrong&selected_flag_tags=team%3Acheckout",
        ):
            assert _get(server, query).status == 404, query
    finally:
        server.close()


@scenarios.test_the_test
def test_forced_ignored_reason_applies_only_to_valid_selections() -> None:
    server = MockedBackendServer()
    try:
        server.client.ffe_use_suite(SUITE)
        server.client.ffe_set_flag_selection_ignored_reason("tag_load_failed")

        response = _get_config(server, "selected_flag_tags=team%3Acheckout")
        assert _flag_keys(response) == SUITE_FLAGS
        assert response.headers[FLAG_SELECTION_IGNORED_HEADER] == "tag_load_failed"

        response = _get_config(server)
        assert FLAG_SELECTION_IGNORED_HEADER not in response.headers

        response = _get_config(server, "selected_flag_tags=%zz")
        assert response.headers[FLAG_SELECTION_IGNORED_HEADER] == "malformed_selection"

        server.client.ffe_set_flag_selection_ignored_reason(None)
        response = _get_config(server, "selected_flag_tags=team%3Acheckout")
        assert _flag_keys(response) == CHECKOUT_FLAGS

        server.client.ffe_set_flag_selection_ignored_reason("future_reason")
        server.client.ffe_reset()
        response = _get_config(server, "selected_flag_tags=team%3Acheckout")
        assert FLAG_SELECTION_IGNORED_HEADER not in response.headers
    finally:
        server.close()


@scenarios.test_the_test
def test_forced_ignored_reason_control_rejects_invalid_bodies() -> None:
    server = MockedBackendServer()
    try:
        for body in ({}, {"ignored_reason": ""}, {"ignored_reason": "a b"}, {"ignored_reason": 1}, {"other": None}):
            response = requests.post(f"{server.base_url}/system-tests/ffe/flag-selection", json=body, timeout=5)
            assert response.status_code == 400, body
    finally:
        server.close()


@scenarios.test_the_test
def test_selection_is_not_applied_to_error_responses() -> None:
    server = MockedBackendServer()
    try:
        server.client.ffe_set_responses(["server_error", "not_modified"])
        for expected_status in (500, 304):
            response = _get(server, f"{CONFIG_QUERY}&selected_flag_tags=%zz", {"If-None-Match": ufc_etag_for(None)})
            assert response.status == expected_status
            assert FLAG_SELECTION_IGNORED_HEADER not in response.headers
    finally:
        server.close()


@scenarios.test_the_test
def test_not_modified_under_a_selection_revalidates_only_its_own_etag() -> None:
    server = MockedBackendServer()
    selection_query = f"{CONFIG_QUERY}&selected_flag_tags=team%3Acheckout"
    try:
        server.client.ffe_use_suite(SUITE)
        server.client.ffe_set_responses(["valid", "not_modified"])
        etag = _get(server, selection_query).headers["ETag"]
        assert etag == ufc_etag_for(Selection(tags=("team:checkout",), key_patterns=()), SUITE)
        assert etag not in {
            ufc_etag_for(None, SUITE),
            ufc_etag_for(Selection(tags=("team:checkout",), key_patterns=())),
        }

        for validator in (etag, f"W/{etag}", f'"other", {etag}'):
            revalidated = _get(server, selection_query, {"If-None-Match": validator})
            assert revalidated.status == 304, validator
            assert revalidated.headers["ETag"] == etag, validator
            assert FLAG_SELECTION_IGNORED_HEADER not in revalidated.headers, validator

        for headers in ({"If-None-Match": ufc_etag_for(None, SUITE)}, {}):
            stale = _get(server, selection_query, headers)
            assert stale.status == 200, headers
            assert stale.headers["ETag"] == etag, headers
            assert _flag_keys(stale) == CHECKOUT_FLAGS, headers
    finally:
        server.close()


@scenarios.test_the_test
def test_not_modified_does_not_confirm_a_selected_body_once_the_selection_is_ignored() -> None:
    server = MockedBackendServer()
    selection_query = f"{CONFIG_QUERY}&selected_flag_tags=team%3Acheckout"
    try:
        server.client.ffe_use_suite(SUITE)
        server.client.ffe_set_responses(["valid", "not_modified"])
        selected_etag = _get(server, selection_query).headers["ETag"]
        server.client.ffe_set_flag_selection_ignored_reason("tag_load_failed")

        response = _get(server, selection_query, {"If-None-Match": selected_etag})
        assert response.status == 200
        assert _flag_keys(response) == SUITE_FLAGS
        assert response.headers[FLAG_SELECTION_IGNORED_HEADER] == "tag_load_failed"
        assert response.headers["ETag"] == ufc_etag_for(None, SUITE)

        revalidated = _get(server, selection_query, {"If-None-Match": ufc_etag_for(None, SUITE)})
        assert revalidated.status == 304
        assert FLAG_SELECTION_IGNORED_HEADER not in revalidated.headers
    finally:
        server.close()


@scenarios.test_the_test
def test_not_modified_without_a_selection_keeps_the_plain_etag() -> None:
    server = MockedBackendServer()
    try:
        server.client.ffe_set_response("not_modified")
        for headers in ({"If-None-Match": ufc_etag_for(None)}, {}):
            response = _get(server, CONFIG_QUERY, headers)
            assert response.status == 304, headers
            assert response.headers["ETag"] == ufc_etag_for(None), headers
    finally:
        server.close()
