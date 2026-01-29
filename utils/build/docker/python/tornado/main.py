import asyncio
import base64
import json
import logging
import os
import sqlite3
import subprocess
import sys
from http import HTTPStatus
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import parse_qs

import ddtrace
import httpx
import psycopg2
import stripe
import tornado
import xmltodict
from ddtrace._trace.pin import Pin
from ddtrace.appsec import trace_utils as appsec_trace_utils
from ddtrace.contrib.trace_utils import set_user
from ddtrace.openfeature import DataDogProvider
from ddtrace.trace import tracer
from iast import (
    weak_cipher,
    weak_cipher_secure_algorithm,
    weak_hash,
    weak_hash_duplicates,
    weak_hash_multiple,
    weak_hash_secure_algorithm,
)
from openfeature import api
from openfeature.evaluation_context import EvaluationContext
from tornado.web import Application, RequestHandler

# Configure logging to output to stderr
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)

# Enable Tornado's access logs
logging.getLogger("tornado.access").setLevel(logging.INFO)
logging.getLogger("tornado.application").setLevel(logging.INFO)
logging.getLogger("tornado.general").setLevel(logging.INFO)

tracer.trace("init.service").finish()

# Configure Stripe client for testing
stripe.api_key = "sk_FAKE"
stripe.api_base = "http://internal_server:8089"

# Configure OpenFeature for FFE
api.set_provider(DataDogProvider())
openfeature_client = api.get_client()

logger = logging.getLogger(__name__)

POSTGRES_CONFIG = {
    "host": "postgres",
    "port": "5433",
    "user": "system_tests_user",
    "password": "system_tests",
    "dbname": "system_tests_dbname",
}

_TRACK_CUSTOM_APPSEC_EVENT_NAME = "system_tests_appsec_event"
_TRACK_METADATA = {"metadata0": "value0", "metadata1": "value1"}
_TRACK_USER = "system_tests_user"


class MainHandler(RequestHandler):
    def get(self) -> None:
        self.write("Hello world!\n")

    def post(self) -> None:
        self.write("Hello world!\n")


class HeadersHandler(RequestHandler):
    def get(self) -> None:
        self.set_header("Content-Type", "text")
        self.set_header("Content-Length", "16")
        self.set_header("Content-Language", "en-US")
        self.write("Hello headers!\n")


class HtmlHandler(RequestHandler):
    def get(self) -> None:
        self.set_header("Content-Type", "text/html")
        self.write(
            """<!DOCTYPE html>
<html>
<head>
    <title>Hello</title>
</head>
<body>
    <h1>Hello</h1>
</body>
</html>""",
        )


class IdentifyHandler(RequestHandler):
    def get(self) -> None:
        set_user(
            tracer,
            user_id="usr.id",
            email="usr.email",
            name="usr.name",
            session_id="usr.session_id",
            role="usr.role",
            scope="usr.scope",
        )
        self.write("OK")


class IdentifyPropagateHandler(RequestHandler):
    def get(self) -> None:
        set_user(
            tracer,
            user_id="usr.id",
            email="usr.email",
            name="usr.name",
            session_id="usr.session_id",
            role="usr.role",
            scope="usr.scope",
            propagate=True,
        )
        self.write("OK")


class ParamsHandler(RequestHandler):
    def get(self, path: str) -> None:  # noqa: ARG002
        self.write("Hello world!\n")


class SampleRateRouteHandler(RequestHandler):
    def get(self, i: str) -> None:  # noqa: ARG002
        self.write("Hello world!\n")


class ApiSecuritySamplingHandler(RequestHandler):
    def get(self, i: str) -> None:  # noqa: ARG002
        self.write("OK\n")


class ApiSecuritySamplingStatusHandler(RequestHandler):
    def get(self, status_code: str) -> None:
        code = int(status_code)
        self.set_status(code)
        if code != HTTPStatus.NO_CONTENT:
            self.write("Hello!\n")


class StatusHandler(RequestHandler):
    def get(self) -> None:
        code = int(self.get_argument("code", "200"))
        self.set_status(code)
        if code != HTTPStatus.NO_CONTENT:
            self.write("OK, probably")


class StatsUniqueHandler(RequestHandler):
    def get(self) -> None:
        code = int(self.get_argument("code", "200"))
        self.set_status(code)
        if code != HTTPStatus.NO_CONTENT:
            self.write("OK, probably")


class HealthcheckHandler(RequestHandler):
    def get(self) -> None:
        self.set_header("Content-Type", "application/json")
        self.write(
            json.dumps(
                {
                    "status": "ok",
                    "library": {"name": "python", "version": ddtrace.__version__},
                },
            ),
        )


class WafHandler(RequestHandler):
    def _handle(self) -> None:
        self.write("Hello world!\n")

    def get(self, path: str | None = None) -> None:  # noqa: ARG002
        self._handle()

    def post(self, path: str | None = None) -> None:  # noqa: ARG002
        self._handle()

    def options(self, path: str | None = None) -> None:  # noqa: ARG002
        self._handle()

    def put(self, path: str | None = None) -> None:  # noqa: ARG002
        self._handle()

    def delete(self, path: str | None = None) -> None:  # noqa: ARG002
        self._handle()

    def patch(self, path: str | None = None) -> None:  # noqa: ARG002
        self._handle()


class TagValueHandler(RequestHandler):
    def _handle(self, tag_value: str, status_code: str) -> None:
        appsec_trace_utils.track_custom_event(
            tracer,
            event_name=_TRACK_CUSTOM_APPSEC_EVENT_NAME,
            metadata={"value": tag_value},
        )
        code = int(status_code)
        for key in self.request.arguments:
            if key not in ("tag_value", "status_code"):
                self.set_header(key, self.get_argument(key))
        self.set_status(code)

        if self.request.method == "POST" and tag_value.startswith("payload_in_response_body"):
            self.set_header("Content-Type", "application/json")
            body = self._parse_body()
            self.write(json.dumps({"payload": body}))
        else:
            self.write("Value tagged")

    def _parse_body(self) -> dict[str, Any]:
        content_type = self.request.headers.get("Content-Type", "")
        body: bytes = self.request.body
        if "application/json" in content_type:
            return json.loads(body)
        if "application/x-www-form-urlencoded" in content_type:
            return {k.decode(): v[-1].decode() for k, v in parse_qs(body).items()}
        return {}

    def get(self, tag_value: str, status_code: str) -> None:
        self._handle(tag_value, status_code)

    def post(self, tag_value: str, status_code: str) -> None:
        self._handle(tag_value, status_code)

    def options(self, tag_value: str, status_code: str) -> None:
        self._handle(tag_value, status_code)


class MakeDistantCallHandler(RequestHandler):
    async def get(self) -> None:
        url = self.get_argument("url")

        async with httpx.AsyncClient() as client:
            response = await client.get(url)

        result = {
            "url": url,
            "status_code": response.status_code,
            "request_headers": dict(response.request.headers),
            "response_headers": dict(response.headers),
        }

        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))


class UsersHandler(RequestHandler):
    def get(self) -> None:
        user = self.get_argument("user")
        set_user(
            tracer,
            user_id=user,
            email="usr.email",
            name="usr.name",
            session_id="usr.session_id",
            role="usr.role",
            scope="usr.scope",
        )
        self.write("OK")


class DbmHandler(RequestHandler):
    def get(self) -> None:
        integration = self.get_argument("integration")
        operation = self.get_argument("operation", "")
        if integration == "psycopg":
            postgres_db = psycopg2.connect(**POSTGRES_CONFIG)
            cursor = postgres_db.cursor()
            if operation == "execute":
                cursor.execute("select 'blah'")
                self.write("OK")
                return
            if operation == "executemany":
                cursor.executemany("select %s", (("blah",), ("moo",)))
                self.write("OK")
                return
            self.set_status(406)
            self.write(f"Cursor method is not supported: {operation}")
            return
        self.set_status(406)
        self.write(f"Integration is not supported: {integration}")


class UserLoginSuccessEventHandler(RequestHandler):
    def get(self) -> None:
        appsec_trace_utils.track_user_login_success_event(
            tracer,
            user_id=_TRACK_USER,
            login=_TRACK_USER,
            metadata=_TRACK_METADATA,
        )
        self.write("OK")


class UserLoginFailureEventHandler(RequestHandler):
    def get(self) -> None:
        appsec_trace_utils.track_user_login_failure_event(
            tracer,
            user_id=_TRACK_USER,
            exists=True,
            metadata=_TRACK_METADATA,
        )
        self.write("OK")


class UserLoginSuccessEventV2Handler(RequestHandler):
    def post(self) -> None:
        try:
            from ddtrace.appsec import track_user_sdk  # noqa: PLC0415
        except ImportError:
            self.set_status(420)
            self.write("KO")
            return

        json_data = json.loads(self.request.body)
        login = json_data.get("login")
        user_id = json_data.get("user_id")
        metadata = json_data.get("metadata")
        track_user_sdk.track_login_success(login=login, user_id=user_id, metadata=metadata)
        self.write("OK")


class UserLoginFailureEventV2Handler(RequestHandler):
    def post(self) -> None:
        try:
            from ddtrace.appsec import track_user_sdk  # noqa: PLC0415
        except ImportError:
            self.set_status(420)
            self.write("KO")
            return

        json_data = json.loads(self.request.body)
        login = json_data.get("login")
        exists = json_data.get("exists") != "false"
        metadata = json_data.get("metadata")
        track_user_sdk.track_login_failure(login=login, exists=exists, metadata=metadata)
        self.write("OK")


class CustomEventHandler(RequestHandler):
    def get(self) -> None:
        appsec_trace_utils.track_custom_event(tracer, event_name="system_tests_event", metadata=_TRACK_METADATA)
        self.write("OK")


class LoginHandler(RequestHandler):
    DB_USER: ClassVar[dict[str, tuple[str, str, str, str]]] = {
        "test": ("social-security-id", "test", "1234", "testuser@ddog.com"),
        "testuuid": (
            "591dc126-8431-4d0f-9509-b23318d3dce4",
            "testuuid",
            "1234",
            "testuseruuid@ddog.com",
        ),
    }

    def _check(self, username: str | None, password: str | None) -> tuple[bool, str | None]:
        if username in self.DB_USER:
            return (self.DB_USER[username][2] == password), self.DB_USER[username][0]
        return False, None

    def _handle(self) -> None:
        username = None
        password = None

        if self.request.method == "POST":
            content_type = self.request.headers.get("Content-Type", "")
            if "application/x-www-form-urlencoded" in content_type:
                username = self.get_body_argument("username", None)
                password = self.get_body_argument("password", None)

        auth = self.request.headers.get("Authorization")
        if auth and auth.startswith("Basic "):
            decoded = base64.b64decode(auth[6:]).decode()
            username, password = decoded.split(":", 1)

        success, user_id = self._check(username, password)
        if success:
            appsec_trace_utils.track_user_login_success_event(
                tracer,
                user_id=user_id,
                login_events_mode="auto",
                login=username,
            )
        elif user_id:
            appsec_trace_utils.track_user_login_failure_event(
                tracer,
                user_id=user_id,
                exists=True,
                login_events_mode="auto",
                login=username,
            )
        else:
            appsec_trace_utils.track_user_login_failure_event(
                tracer,
                user_id=username,
                exists=False,
                login_events_mode="auto",
                login=username,
            )

        sdk_event = self.get_argument("sdk_event", None)
        if sdk_event:
            sdk_user = self.get_argument("sdk_user", None)
            sdk_mail = self.get_argument("sdk_mail", None)
            sdk_user_exists = self.get_argument("sdk_user_exists", None) == "true"
            if sdk_event == "success":
                appsec_trace_utils.track_user_login_success_event(
                    tracer,
                    user_id=sdk_user,
                    email=sdk_mail,
                    login=sdk_user,
                )
                success = True
            elif sdk_event == "failure":
                appsec_trace_utils.track_user_login_failure_event(
                    tracer,
                    user_id=sdk_user,
                    email=sdk_mail,
                    exists=sdk_user_exists,
                    login=sdk_user,
                )

        if success:
            self.write("OK")
        else:
            self.set_status(401)
            self.write("login failure")

    def get(self) -> None:
        self._handle()

    def post(self) -> None:
        self._handle()


class SetCookieHandler(RequestHandler):
    def get(self) -> None:
        name = self.get_argument("name")
        value = self.get_argument("value")
        self.set_cookie(name, value)
        self.write("OK")


class SessionNewHandler(RequestHandler):
    def get(self) -> None:
        session_id = "random_session_id"
        self.set_cookie("session_id", session_id)
        self.write(session_id)


class SessionUserHandler(RequestHandler):
    def get(self) -> None:
        user = self.get_argument("sdk_user", "")
        session_cookie = self.get_cookie("session_id", "")
        if user and session_cookie == "random_session_id":
            appsec_trace_utils.track_user_login_success_event(tracer, user_id=user, session_id=f"session_{user}")
        self.write("OK")


# RASP Handlers
def _get_rasp_param(handler: RequestHandler, key: str) -> str | None:
    if handler.request.method == "GET":
        return handler.get_argument(key, None)
    content_type = handler.request.headers.get("Content-Type", "")
    body = handler.request.body
    if not body:
        return None
    if "application/json" in content_type:
        data = json.loads(body)
        return data.get(key)
    if "application/xml" in content_type:
        data = xmltodict.parse(body)
        param = data.get(key)
        if key == "command":
            param = param.get("cmd")
        return param
    if "application/x-www-form-urlencoded" in content_type:
        return handler.get_body_argument(key, None)
    return None


class RaspLfiHandler(RequestHandler):
    def _handle(self) -> None:
        file_path = _get_rasp_param(self, "file")
        if file_path is None:
            self.set_status(400)
            self.write("missing file parameter")
            return
        try:
            with open(file_path, "rb") as f:  # noqa: PTH123
                f.seek(0, os.SEEK_END)
                self.write(f"{file_path} open with {f.tell()} bytes")
        except OSError as e:
            self.write(f"{file_path} could not be open: {e!r}")

    def get(self) -> None:
        self._handle()

    def post(self) -> None:
        self._handle()


class RaspSsrfHandler(RequestHandler):
    async def _handle(self) -> None:
        domain = _get_rasp_param(self, "domain")
        if domain is None:
            self.set_status(400)
            self.write("missing domain parameter")
            return
        url = f"http://{domain}"
        try:
            async with httpx.AsyncClient(timeout=1) as client:
                response = await client.get(url)
                content = response.content
                self.write(f"url {url} open with {len(content)} bytes")
        except Exception as e:  # noqa: BLE001
            self.write(f"url {url} could not be open: {e!r}")

    async def get(self) -> None:
        await self._handle()

    async def post(self) -> None:
        await self._handle()


class RaspSqliHandler(RequestHandler):
    def _handle(self) -> None:
        user_id = _get_rasp_param(self, "user_id")
        if user_id is None:
            self.set_status(400)
            self.write("missing user_id parameter")
            return
        try:
            db = sqlite3.connect(":memory:")
            cursor = db.execute(f"SELECT * FROM users WHERE id='{user_id}'")  # noqa: S608
            self.write(f"DB request with {len(list(cursor))} results")
        except Exception as e:  # noqa: BLE001
            self.set_status(201)
            self.write(f"DB request failure: {e!r}")

    def get(self) -> None:
        self._handle()

    def post(self) -> None:
        self._handle()


class RaspShiHandler(RequestHandler):
    def _handle(self) -> None:
        list_dir = _get_rasp_param(self, "list_dir")
        if list_dir is None:
            self.set_status(400)
            self.write("missing list_dir parameter")
            return
        try:
            command = f"ls {list_dir}"
            res = os.system(command)  # noqa: S605
            self.write(f"Shell command [{command}] with result: {res}")
        except Exception as e:  # noqa: BLE001
            self.set_status(201)
            self.write(f"Shell command failure: {e!r}")

    def get(self) -> None:
        self._handle()

    def post(self) -> None:
        self._handle()


class RaspCmdiHandler(RequestHandler):
    def _handle(self) -> None:
        cmd = _get_rasp_param(self, "command")
        logger.info("And the cmd is %r", cmd)
        if cmd is None:
            self.set_status(400)
            self.write("missing command parameter")
            return
        if isinstance(cmd, dict) and "cmd" in cmd:
            cmd = cmd.get("cmd")
        try:
            res = subprocess.run(cmd, check=False, capture_output=True)  # noqa: S603
            self.write(f"Exec command [{cmd}] with result: {res}")
        except Exception as e:  # noqa: BLE001
            self.set_status(201)
            self.write(f"Exec command [{cmd}] failure: {e!r}")

    def get(self) -> None:
        self._handle()

    def post(self) -> None:
        self._handle()


class RaspMultipleHandler(RequestHandler):
    def _handle(self) -> None:
        file1 = self.get_argument("file1", None)
        file2 = self.get_argument("file2", None)
        if file1 is None or file2 is None:
            self.set_status(400)
            self.write("missing file1 or file2 parameter")
            return
        lengths = []
        for file_path in [file1, file2, "../etc/passwd"]:
            try:
                with Path(file_path).open("rb") as f:
                    f.seek(0, os.SEEK_END)
                    lengths.append(f.tell())
            except Exception:  # noqa: BLE001
                lengths.append(0)
        self.write(f"files open with {lengths} bytes")

    def get(self) -> None:
        self._handle()

    def post(self) -> None:
        self._handle()


# IAST Handlers
class IastInsecureHashingMultipleHandler(RequestHandler):
    def get(self) -> None:
        weak_hash_multiple()
        self.write("OK")


class IastInsecureHashingSecureHandler(RequestHandler):
    def get(self) -> None:
        weak_hash_secure_algorithm()
        self.write("OK")


class IastInsecureHashingMd5Handler(RequestHandler):
    def get(self) -> None:
        weak_hash()
        self.write("OK")


class IastInsecureHashingDeduplicateHandler(RequestHandler):
    def get(self) -> None:
        weak_hash_duplicates()
        self.write("OK")


class IastInsecureCipherInsecureHandler(RequestHandler):
    def get(self) -> None:
        weak_cipher()
        self.write("OK")


class IastInsecureCipherSecureHandler(RequestHandler):
    def get(self) -> None:
        weak_cipher_secure_algorithm()
        self.write("OK")


class IastInsecureCookieInsecureHandler(RequestHandler):
    def get(self) -> None:
        self.set_cookie("insecure", "cookie", secure=False, httponly=False, samesite="None")
        self.write("OK")


class IastInsecureCookieSecureHandler(RequestHandler):
    def get(self) -> None:
        self.set_cookie("secure3", "value", secure=True, httponly=True, samesite="Strict")
        self.write("OK")


class IastInsecureCookieEmptyHandler(RequestHandler):
    def get(self) -> None:
        self.set_cookie("secure3", "", secure=True, httponly=True, samesite="Strict")
        self.write("OK")


class IastNoHttpOnlyCookieInsecureHandler(RequestHandler):
    def get(self) -> None:
        self.set_cookie("insecure", "cookie", secure=True, httponly=False, samesite="Strict")
        self.write("OK")


class IastNoHttpOnlyCookieSecureHandler(RequestHandler):
    def get(self) -> None:
        self.set_cookie("secure3", "value", secure=True, httponly=True, samesite="Strict")
        self.write("OK")


class IastNoHttpOnlyCookieEmptyHandler(RequestHandler):
    def get(self) -> None:
        self.set_cookie("secure3", "", secure=True, httponly=True, samesite="Strict")
        self.write("OK")


class IastNoSameSiteCookieInsecureHandler(RequestHandler):
    def get(self) -> None:
        self.set_cookie("insecure", "cookie", secure=True, httponly=True, samesite="None")
        self.write("OK")


class IastNoSameSiteCookieSecureHandler(RequestHandler):
    def get(self) -> None:
        self.set_cookie("secure3", "value", secure=True, httponly=True, samesite="Strict")
        self.write("OK")


class IastNoSameSiteCookieEmptyHandler(RequestHandler):
    def get(self) -> None:
        self.set_cookie("secure3", "", secure=True, httponly=True, samesite="None")
        self.write("OK")


# Downstream request handlers
class RequestDownstreamHandler(RequestHandler):
    async def _handle(self) -> None:
        url = "http://localhost:7777/returnheaders"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url)
                self.write(response.content)
        except Exception as e:  # noqa: BLE001
            self.write(f"Error: {e!r}")

    async def get(self) -> None:
        await self._handle()

    async def post(self) -> None:
        await self._handle()

    async def options(self) -> None:
        await self._handle()


class VulnerableRequestDownstreamHandler(RequestHandler):
    async def _handle(self) -> None:
        weak_hash()
        url = "http://localhost:7777/returnheaders"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url)
                self.write(response.content)
        except Exception as e:  # noqa: BLE001
            self.write(f"Error: {e!r}")

    async def get(self) -> None:
        await self._handle()

    async def post(self) -> None:
        await self._handle()

    async def options(self) -> None:
        await self._handle()


class ReturnHeadersHandler(RequestHandler):
    def _handle(self) -> None:
        headers = dict(self.request.headers.items())
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(headers))

    def get(self) -> None:
        self._handle()

    def post(self) -> None:
        self._handle()

    def options(self) -> None:
        self._handle()


class CreateExtraServiceHandler(RequestHandler):
    def get(self) -> None:
        service_name = self.get_argument("serviceName", "")
        if service_name:
            Pin.override(tornado, service=service_name)
        self.write("OK")


class ResourceRenamingHandler(RequestHandler):
    def get(self, path: str | None = None) -> None:  # noqa: ARG002
        self.write("ok")


class StripeCreateCheckoutSessionHandler(RequestHandler):
    async def post(self) -> None:
        try:
            body = json.loads(self.request.body)
            result = stripe.checkout.Session.create(**body)
            self.set_header("Content-Type", "application/json")
            self.write(json.dumps(dict(result)))
        except Exception as e:  # noqa: BLE001
            self.set_status(500)
            self.set_header("Content-Type", "application/json")
            self.write(json.dumps({"error": str(e)}))


class StripeCreatePaymentIntentHandler(RequestHandler):
    async def post(self) -> None:
        try:
            body = json.loads(self.request.body)
            result = stripe.PaymentIntent.create(**body)
            self.set_header("Content-Type", "application/json")
            self.write(json.dumps(dict(result)))
        except Exception as e:  # noqa: BLE001
            self.set_status(500)
            self.set_header("Content-Type", "application/json")
            self.write(json.dumps({"error": str(e)}))


class StripeWebhookHandler(RequestHandler):
    async def post(self) -> None:
        try:
            signature = self.request.headers.get("Stripe-Signature")
            event = stripe.Webhook.construct_event(self.request.body, signature, "whsec_FAKE")
            self.set_header("Content-Type", "application/json")
            self.write(json.dumps(event.data.object))
        except Exception as e:  # noqa: BLE001
            self.set_status(403)
            self.set_header("Content-Type", "application/json")
            self.write(json.dumps({"error": str(e)}))


class ExternalRequestHandler(RequestHandler):
    SUPPORTED_METHODS = ("GET", "POST", "PUT", "TRACE")

    async def _handle(self) -> None:
        # Get query parameters - convert to dict for headers
        queries = {k: str(v[0]) for k, v in self.request.arguments.items()}
        status = queries.pop("status", "200")
        url_extra = queries.pop("url_extra", "")

        # Build the URL
        url = f"http://internal_server:8089/mirror/{status}{url_extra}"

        # Prepare request body
        body = self.request.body or None
        if body:
            queries["Content-Type"] = self.request.headers.get("Content-Type") or "application/json"

        # Make the request
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.request(
                    method=self.request.method,
                    url=url,
                    headers=queries,
                    content=body,
                )
                payload = response.text
                result = {
                    "status": int(response.status_code),
                    "headers": dict(response.headers.items()),
                    "payload": json.loads(payload),
                }
        except httpx.HTTPStatusError as e:
            result = {
                "status": int(e.response.status_code) if e.response else None,
                "error": repr(e),
            }
        except Exception as e:  # noqa: BLE001
            result = {
                "status": None,
                "error": repr(e),
            }

        self.set_status(200)
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))

    async def get(self) -> None:
        await self._handle()

    async def post(self) -> None:
        await self._handle()

    async def put(self) -> None:
        await self._handle()

    async def trace(self) -> None:
        await self._handle()


class ExternalRequestRedirectHandler(RequestHandler):
    async def get(self) -> None:
        queries = {k: str(v[0]) for k, v in self.request.arguments.items()}
        total_redirects = queries.get("totalRedirects", "0")

        url = f"http://internal_server:8089/redirect?totalRedirects={total_redirects}"

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, headers=queries)
                payload = response.text
                result = {
                    "status": int(response.status_code),
                    "headers": dict(response.headers.items()),
                    "payload": json.loads(payload),
                }
        except httpx.HTTPStatusError as e:
            result = {
                "status": int(e.response.status_code) if e.response else None,
                "error": repr(e),
            }
        except Exception as e:  # noqa: BLE001
            result = {
                "status": None,
                "error": repr(e),
            }

        self.set_status(200)
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))


class FfeHandler(RequestHandler):
    """OpenFeature evaluation endpoint for Feature Flag Evaluation (FFE)."""

    def post(self) -> None:
        body = json.loads(self.request.body)
        flag = body.get("flag")
        variation_type = body.get("variationType")
        default_value = body.get("defaultValue")
        targeting_key = body.get("targetingKey")
        attributes = body.get("attributes", {})

        # Build context
        context = EvaluationContext(targeting_key=targeting_key, attributes=attributes)

        # Evaluate based on variation type
        if variation_type == "BOOLEAN":
            value = openfeature_client.get_boolean_value(flag, default_value, context)
        elif variation_type == "STRING":
            value = openfeature_client.get_string_value(flag, default_value, context)
        elif variation_type in ("INTEGER", "NUMERIC"):
            value = openfeature_client.get_integer_value(flag, default_value, context)
        elif variation_type == "JSON":
            value = openfeature_client.get_object_value(flag, default_value, context)
        else:
            self.set_status(400)
            self.set_header("Content-Type", "application/json")
            self.write(json.dumps({"error": f"Unknown variation type: {variation_type}"}))
            return

        self.set_status(200)
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps({"value": value}))


def make_app() -> Application:
    return Application(
        [
            # Core endpoints
            (r"/", MainHandler),
            (r"/headers", HeadersHandler),
            (r"/html", HtmlHandler),
            (r"/identify", IdentifyHandler),
            (r"/identify-propagate", IdentifyPropagateHandler),
            (r"/params/(.+)", ParamsHandler),
            (r"/sample_rate_route/(\d+)", SampleRateRouteHandler),
            (r"/api_security_sampling/(\d+)", ApiSecuritySamplingHandler),
            (r"/api_security/sampling/(\d+)", ApiSecuritySamplingStatusHandler),
            (r"/status", StatusHandler),
            (r"/stats-unique", StatsUniqueHandler),
            (r"/healthcheck", HealthcheckHandler),
            # WAF endpoints
            (r"/waf/?", WafHandler),
            (r"/waf/(.+)", WafHandler),
            # Tag value endpoint
            (r"/tag_value/(?P<tag_value>[^/]+)/(?P<status_code>\d+)", TagValueHandler),
            # HTTP client endpoints
            (r"/make_distant_call", MakeDistantCallHandler),
            (r"/external_request", ExternalRequestHandler),
            (r"/external_request/redirect", ExternalRequestRedirectHandler),
            # Feature Flag Evaluation endpoints
            (r"/ffe", FfeHandler),
            # User endpoints
            (r"/users", UsersHandler),
            (r"/login", LoginHandler),
            (r"/set_cookie", SetCookieHandler),
            # Session endpoints
            (r"/session/new", SessionNewHandler),
            (r"/session/user", SessionUserHandler),
            # Event tracking endpoints
            (r"/user_login_success_event", UserLoginSuccessEventHandler),
            (r"/user_login_failure_event", UserLoginFailureEventHandler),
            (r"/user_login_success_event_v2", UserLoginSuccessEventV2Handler),
            (r"/user_login_failure_event_v2", UserLoginFailureEventV2Handler),
            (r"/custom_event", CustomEventHandler),
            # Database endpoints
            (r"/dbm", DbmHandler),
            # RASP endpoints
            (r"/rasp/lfi", RaspLfiHandler),
            (r"/rasp/ssrf", RaspSsrfHandler),
            (r"/rasp/sqli", RaspSqliHandler),
            (r"/rasp/shi", RaspShiHandler),
            (r"/rasp/cmdi", RaspCmdiHandler),
            (r"/rasp/multiple", RaspMultipleHandler),
            # IAST Insecure hashing endpoints
            (
                r"/iast/insecure_hashing/multiple_hash",
                IastInsecureHashingMultipleHandler,
            ),
            (
                r"/iast/insecure_hashing/test_secure_algorithm",
                IastInsecureHashingSecureHandler,
            ),
            (
                r"/iast/insecure_hashing/test_md5_algorithm",
                IastInsecureHashingMd5Handler,
            ),
            (
                r"/iast/insecure_hashing/deduplicate",
                IastInsecureHashingDeduplicateHandler,
            ),
            # IAST Insecure cipher endpoints
            (
                r"/iast/insecure_cipher/test_insecure_algorithm",
                IastInsecureCipherInsecureHandler,
            ),
            (
                r"/iast/insecure_cipher/test_secure_algorithm",
                IastInsecureCipherSecureHandler,
            ),
            # IAST Cookie endpoints
            (r"/iast/insecure-cookie/test_insecure", IastInsecureCookieInsecureHandler),
            (r"/iast/insecure-cookie/test_secure", IastInsecureCookieSecureHandler),
            (
                r"/iast/insecure-cookie/test_empty_cookie",
                IastInsecureCookieEmptyHandler,
            ),
            (
                r"/iast/no-httponly-cookie/test_insecure",
                IastNoHttpOnlyCookieInsecureHandler,
            ),
            (
                r"/iast/no-httponly-cookie/test_secure",
                IastNoHttpOnlyCookieSecureHandler,
            ),
            (
                r"/iast/no-httponly-cookie/test_empty_cookie",
                IastNoHttpOnlyCookieEmptyHandler,
            ),
            (
                r"/iast/no-samesite-cookie/test_insecure",
                IastNoSameSiteCookieInsecureHandler,
            ),
            (
                r"/iast/no-samesite-cookie/test_secure",
                IastNoSameSiteCookieSecureHandler,
            ),
            (
                r"/iast/no-samesite-cookie/test_empty_cookie",
                IastNoSameSiteCookieEmptyHandler,
            ),
            # Downstream request endpoints
            (r"/requestdownstream/?", RequestDownstreamHandler),
            (r"/vulnerablerequestdownstream/?", VulnerableRequestDownstreamHandler),
            (r"/returnheaders/?", ReturnHeadersHandler),
            # Service endpoints
            (r"/createextraservice", CreateExtraServiceHandler),
            (r"/resource_renaming/(.*)", ResourceRenamingHandler),
            # Stripe endpoints
            (r"/stripe/create_checkout_session", StripeCreateCheckoutSessionHandler),
            (r"/stripe/create_payment_intent", StripeCreatePaymentIntentHandler),
            (r"/stripe/webhook", StripeWebhookHandler),
        ],
        debug=False,
    )


async def main() -> None:
    app = make_app()
    app.listen(7777, address="0.0.0.0")  # noqa: S104
    await asyncio.Event().wait()


if __name__ == "__main__":
    logger.info("Tornado weblog started on port 7777")
    asyncio.run(main())
