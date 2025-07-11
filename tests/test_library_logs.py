# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, interfaces, irrelevant, features
import itertools
import re
from re import Pattern


def matches_any(patterns: list[Pattern], string: str):
    return any(re.fullmatch(pattern, string) for pattern in patterns)


@features.not_reported
class Test_NoExceptions:
    """No unexpected exceptions or errors."""

    @irrelevant(context.library != "dotnet", reason="only for .NET")
    def test_dotnet(self):
        """There is not exception in dotnet-tracer-managed log files"""
        interfaces.library_dotnet_managed.assert_absence(
            pattern=r"[A-Za-z]+\.[A-Za-z]*Exception",
            allowed_patterns=[
                r"System.DllNotFoundException: Unable to load shared library 'Datadog.AutoInstrumentation.Profiler.Native.x64'",  # pylint: disable=line-too-long
                r"Logger retrieved for: Datadog.Trace.Debugger.ExceptionAutoInstrumentation.ExceptionDebugging",  # pylint: disable=line-too-long
            ],
        )

    @irrelevant(context.library != "java", reason="only for Java")
    def test_java_logs(self):
        """Test Java logs for unexpected errors."""
        disallowed_patterns = [
            r".*ERROR.*",
            r".*WARN powerwaf_native.*",
            r".*WARN ddwaf_native.*",
        ]
        allowed_patterns = [
            r".*"
            + re.escape(
                "Skipped authentication, auth=org.springframework.security.authentication.AnonymousAuthenticationToken"
            ),
            # APPSEC-56726:
            r".*" + re.escape("Attempt to replace context value for Address{key='usr.login'}"),
            # APPSEC-56727:
            r".*org.hsqldb.HsqlException.*",
            # APPSEC-56728:
            r".*getWriter.* has already been called for this response.*",
            # APPSEC-56729:
            r".*java.lang.NullPointerException: null.*at com.datadoghq.system_tests.iast.utils.SqlExamples.fetchUsers.*",
            # APPSEC-56899:
            r".*WARN powerwaf_native - Failed to replace non-ephemeral target 'usr.id' with an ephemeral one.*",
            r".*WARN ddwaf_native - Failed to replace non-ephemeral target 'usr.id' with an ephemeral one.*",
            r".*Failed to find the jdk.internal.jvmstat module.*",
        ]
        if context.weblog_variant == "spring-boot-openliberty":
            # XXX: openliberty logs are more noisy for some unexpected errors,
            # there are many endpoints in spring-boot weblog to fix.
            allowed_patterns += [
                r".*class java.util.LinkedHashMap.*",
                r".*UnknownHostException: cassandra.*",
                # XXX: This background warning occasionally gets printed in the
                # middle of an unrelated error, breaing multi-line log parsing,
                # and producing spurious failures.
                ".*Using native clock.*",
                # AIDM-588:
                r".*Critical issue initializing instances: javax.management.JMRuntimeException.*",
                r".*org.datadog.jmxfetch.App.*",
            ]
        elif context.weblog_variant == "spring-boot-undertow":
            # APPSEC-56802:
            allowed_patterns.append(r".*UT005023.*")
        compiled_allowed_paterns = [re.compile(p, re.MULTILINE | re.DOTALL) for p in allowed_patterns]
        compiled_disallowed_paterns = [re.compile(p, re.MULTILINE | re.DOTALL) for p in disallowed_patterns]
        logs = list(interfaces.library_stdout.get_data())
        logs = list({log["raw"] for log in logs})
        logs = [log for log in logs if matches_any(compiled_disallowed_paterns, log)]
        logs = [log for log in logs if not matches_any(compiled_allowed_paterns, log)]
        assert not logs

    @irrelevant(context.library != "java", reason="only for Java")
    def test_java_telemetry_logs(self):
        """Test Java telemetry logs for unexpected errors."""
        allowed_patterns = [
            re.escape("Skipped authentication, auth={}"),
            # APPSEC-56726:
            re.escape("Attempt to replace context value for {}"),
            r"Failed to find the jdk.internal\.jvmstat module.*",
        ]
        if context.weblog_variant == "spring-boot-openliberty":
            # AIDM-588:
            allowed_patterns.append(re.escape("JMXFetch internal TaskProcessor error invoking concurrent tasks: "))
        if context.weblog_variant == "spring-boot-wildfly":
            # APPSEC-56111:
            allowed_patterns.append(re.escape("Failed to determine dependency for uri {}"))
        if context.weblog_variant in ("vertx3", "vertx4"):
            # AIDM-583:
            allowed_patterns.append(
                re.escape(
                    "Failed to handle exception in instrumentation for io.netty.handler.codec.http.multipart.HttpPostMultipartRequestDecoder"
                )
            )
        compiled_paterns = [re.compile(p, re.MULTILINE | re.DOTALL) for p in allowed_patterns]
        data = interfaces.library.get_telemetry_data()
        data = [d["request"]["content"] for d in data]
        data = [d["payload"]["logs"] for d in data if d.get("request_type") == "logs"]
        data = list(itertools.chain(*data))
        data = [d for d in data if not matches_any(compiled_paterns, d["message"])]
        assert not data
