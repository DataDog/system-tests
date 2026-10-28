"""Local EVP fault receiver. Captures happen before rejection or connection loss."""

from collections.abc import Mapping
from http import HTTPStatus
import socket
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ._request_handler import MockBackendV2RequestHandler, MockedBackendServerCore


def configure_evp_receiver(server: "MockedBackendServerCore") -> None:
    for mode in ("404", "405", "403", "ambiguous"):
        for signal in ("exposures", "flagevaluation"):
            prefix = f"/evp-test/{mode}/{signal}"
            server.add_handler("GET", f"{prefix}/info", _info)
            for endpoint in ("exposures", "flagevaluation"):
                server.add_handler("POST", f"{prefix}/evp_proxy/v4/api/v2/{endpoint}", _delivery)


def _info(request: "MockBackendV2RequestHandler", _: bytes | dict | None) -> tuple[Mapping[str, Any], bytes]:
    return request.write_json(
        HTTPStatus.OK,
        {
            "endpoints": ["/evp_proxy/v2", "/evp_proxy/v4"],
            "evp_proxy_allowed_headers": ["dd-evp-origin", "Dd-Evp-Origin-Version"],
        },
    )


def _delivery(request: "MockBackendV2RequestHandler", _: bytes | dict | None) -> tuple[Mapping[str, Any], bytes]:
    parts = request.path.split("/")
    mode, target = parts[2:4]
    if request.path.endswith(f"/{target}"):
        if mode == "ambiguous":
            # The entire request body has arrived; the sender cannot know whether it was accepted.
            request.close_connection = True
            request.connection.shutdown(socket.SHUT_RDWR)
            return {}, b""
        return request.write_json(HTTPStatus(int(mode)), {})
    return request.write_json(HTTPStatus.ACCEPTED, {})
