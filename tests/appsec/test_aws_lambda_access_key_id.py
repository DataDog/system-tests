# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2026 Datadog, Inc.

"""RFC "CADR for AWS Lambda", scenarios S1, S2, S3, S7 and S8 (JULIO-11 cross-component prototype)"""

import json

from utils import features, interfaces, scenarios, weblog
from utils._context._scenarios.aws_lambda import AWS_LAMBDA_ACCESS_KEY_ID, AWS_LAMBDA_CREDENTIAL_CANARIES
from utils._weblog import HttpResponse
from utils.dd_types import DataDogAgentSpan, DataDogLibrarySpan

TAG = "aws.lambda.access_key_id"


def _backend_invocation_spans(request: HttpResponse) -> list[DataDogAgentSpan]:
    """The aws.lambda spans of this request, as the extension sent them to the backend"""
    spans = [span for span in interfaces.mocked_backend.get_spans_list(request) if span.get_span_name() == "aws.lambda"]
    assert spans, "No aws.lambda span found for the request"
    return spans


def _tracer_invocation_spans(request: HttpResponse | None) -> list[DataDogLibrarySpan]:
    """The aws.lambda spans of this request (or of all requests), as the tracer sent them to the extension"""
    spans = [span for _, _, span in interfaces.library.get_spans(request) if span["name"] == "aws.lambda"]
    assert spans, "No aws.lambda span found for the request"
    return spans


@features.appsec_aws_lambda_access_key_id
@scenarios.appsec_lambda_aws_access_key_id
@scenarios.appsec_lambda_aws_access_key_id_extension
class Test_AwsLambdaAccessKeyId:
    """S1: the invocation span carries the execution environment's AWS access key ID"""

    def setup_tag_on_normal_request(self):
        self.r = weblog.get("/")

    def test_tag_on_normal_request(self):
        assert self.r.status_code == 200
        for span in _backend_invocation_spans(self.r):
            assert span.get_tag(TAG) == AWS_LAMBDA_ACCESS_KEY_ID, f"{TAG} missing or wrong on {span.raw_span}"

    def setup_tag_on_attack(self):
        self.r_attack = weblog.get("/", params={"file": "/proc/self/environ"})

    def test_tag_on_attack(self):
        """S7: the AppSec event is raised as before, and the span carries the tag"""
        found_event = False
        for _, span, appsec_data in interfaces.mocked_backend.get_appsec_data(self.r_attack):
            if span.get_span_name() != "aws.lambda":
                continue
            data = json.loads(appsec_data) if isinstance(appsec_data, str) else appsec_data
            rule_ids = {trigger["rule"]["id"] for trigger in data["triggers"]}
            assert "crs-930-120" in rule_ids, rule_ids
            assert span.get_tag(TAG) == AWS_LAMBDA_ACCESS_KEY_ID
            found_event = True
        assert found_event, "No AppSec event on the aws.lambda span"


@features.appsec_aws_lambda_access_key_id
@scenarios.appsec_lambda_aws_access_key_id
class Test_AwsLambdaAccessKeyId_TracerPath:
    """S8: with tracer AppSec, the tracer sets the tag"""

    def setup_tracer_sets_tag(self):
        self.r = weblog.get("/")

    def test_tracer_sets_tag(self):
        for span in _tracer_invocation_spans(self.r):
            assert span["meta"].get(TAG) == AWS_LAMBDA_ACCESS_KEY_ID


@features.appsec_aws_lambda_access_key_id
@scenarios.appsec_lambda_aws_access_key_id_extension
class Test_AwsLambdaAccessKeyId_ExtensionPath:
    """S8: with extension AppSec, tracer AppSec is off and only the extension sets the tag"""

    def setup_extension_sets_tag(self):
        self.r = weblog.get("/")

    def test_extension_sets_tag(self):
        # without tracer AppSec, the tracer span does not carry the request ID: check every invocation
        for tracer_span in _tracer_invocation_spans(None):
            assert TAG not in tracer_span["meta"], "The tracer set the tag: tracer AppSec is still on"
            assert "_dd.appsec.enabled" not in tracer_span.get("metrics", {}), "Tracer AppSec is still on"
        for backend_span in _backend_invocation_spans(self.r):
            assert backend_span.get_tag(TAG) == AWS_LAMBDA_ACCESS_KEY_ID


@features.appsec_aws_lambda_access_key_id
@scenarios.appsec_lambda_aws_access_key_id
@scenarios.appsec_lambda_aws_access_key_id_extension
@scenarios.appsec_lambda_aws_access_key_id_default
class Test_AwsLambdaAccessKeyId_NoSecret:
    """S3: neither the secret access key nor the session token leaves the function"""

    def setup_no_canary(self):
        self.r = weblog.get("/", params={"file": "/proc/self/environ"})

    def test_no_canary(self):
        assert self.r.status_code in (200, 403)
        checked = 0
        for interface in (interfaces.library, interfaces.mocked_backend):
            for data in interface.get_data():
                raw = json.dumps(data["request"], default=str)
                checked += 1
                for canary in AWS_LAMBDA_CREDENTIAL_CANARIES:
                    assert canary not in raw, f"{canary} found in {data['log_filename']}"
        assert checked > 0
        for canary in AWS_LAMBDA_CREDENTIAL_CANARIES:
            interfaces.library_stdout.assert_absence(canary)


@features.appsec_aws_lambda_access_key_id
@scenarios.appsec_lambda_aws_access_key_id_default
class Test_AwsLambdaAccessKeyId_DefaultOff:
    """S2: valid credentials, DD_APPSEC_AWS_ACCESS_KEY_ID_ENABLED unset: no span carries the tag"""

    def setup_no_tag_by_default(self):
        self.r = weblog.get("/")

    def test_no_tag_by_default(self):
        assert self.r.status_code == 200
        for span in _backend_invocation_spans(self.r):
            assert "_dd.appsec.enabled" in span.metrics, "AppSec is not on: the test would pass vacuously"
            assert TAG not in span.meta
