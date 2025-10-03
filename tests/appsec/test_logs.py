# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
# Test modification

from utils import weblog, context, interfaces, missing_feature, features, bug

# get the default log output
stdout = interfaces.library_stdout if context.library != "dotnet" else interfaces.library_dotnet_managed


@features.appsec_logs
class Test_Standardization:
    """AppSec logs should be standardized"""

    def setup_d05(self):
        weblog.get("/waf", params={"key": "\n :"})  # rules.http_protocol_violation.crs_921_160
        weblog.get("/waf", headers={"random-key": "acunetix-user-agreement"})  # rules.security_scanner.crs_913_110

    @missing_feature(library="php")
    @missing_feature(library="dotnet", reason="APPSEC-983, being discussed")
    @bug(library="java", reason="APPSEC-55157")
    def test_i01(self):
        """Log I1: AppSec initial configuration"""
        stdout.assert_presence(r"AppSec initial configuration from .*, libddwaf version: \d+\.\d+\.\d+", level="INFO")

    @missing_feature(library="php", reason="rules are not analyzed, only converted to PWArgs")
    @bug(library="java", reason="APPSEC-55157")
    def test_i02(self):
        """Log I2: AppSec rule source"""
        stdout.assert_presence(r"AppSec loaded \d+ rules from file .*$", level="INFO")

    @missing_feature(library="dotnet", reason="APPSEC-983")
    @missing_feature(context.library <= "java@0.88.0", reason="small typo")
    @missing_feature(library="php")
    @bug(library="java", reason="APPSEC-55157")
    def test_i05(self):
        """Log I5: WAF detected an attack"""
        stdout.assert_presence(r"Detecting an attack from rule crs-921-160$", level="INFO")
        stdout.assert_presence(r"Detecting an attack from rule crs-913-110$", level="INFO")


@features.appsec_logs
class Test_StandardizationBlockMode:
    """AppSec blocking logs should be standardized"""

    def setup_i06(self):
        """Send a bunch of attack, to be sure that something is done on AppSec side"""

        weblog.get("/waf", params={"key": "\n :"})  # rules.http_protocol_violation.crs_921_160
        weblog.get("/waf", headers={"random-key": "acunetix-user-agreement"})  # rules.security_scanner.crs_913_110

    def test_i06(self):
        """Log I6: AppSec blocked a request"""
        stdout.assert_presence(r"Blocking current transaction \(rule: .*\)$", level="INFO")
