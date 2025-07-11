# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

# Automatic generatiom from:
#    python utils/scripts/extract_appsec_waf_rules.py


from enum import StrEnum


class security_scanner(StrEnum):
    crs_913_110 = "crs-913-110"  # Acunetix
    crs_913_120 = "crs-913-120"  # Known security scanner filename/argument
    nfd_000_001 = "nfd-000-001"  # Detect common directory discovery scans
    nfd_000_002 = "nfd-000-002"  # Detect failed attempt to fetch readme files
    nfd_000_003 = "nfd-000-003"  # Detect failed attempt to fetch Java EE resource files
    nfd_000_004 = "nfd-000-004"  # Detect failed attempt to fetch code files
    nfd_000_005 = "nfd-000-005"  # Detect failed attempt to fetch source code archives
    nfd_000_006 = "nfd-000-006"  # Detect failed attempt to fetch sensitive files
    nfd_000_007 = "nfd-000-007"  # Detect failed attempt to fetch archives
    nfd_000_008 = "nfd-000-008"  # Detect failed attempt to trigger incorrect application behavior
    nfd_000_009 = "nfd-000-009"  # Detect failed attempt to leak the structure of the application
    ua0_600_0xx = "ua0-600-0xx"  # Joomla exploitation tool
    ua0_600_10x = "ua0-600-10x"  # Nessus
    ua0_600_12x = "ua0-600-12x"  # Arachni
    ua0_600_13x = "ua0-600-13x"  # Jorgee
    ua0_600_14x = "ua0-600-14x"  # Probely
    ua0_600_15x = "ua0-600-15x"  # Metis
    ua0_600_16x = "ua0-600-16x"  # SQL power injector
    ua0_600_18x = "ua0-600-18x"  # N-Stealth
    ua0_600_19x = "ua0-600-19x"  # Brutus
    ua0_600_1xx = "ua0-600-1xx"  # Shellshock exploitation tool
    ua0_600_20x = "ua0-600-20x"  # Netsparker
    ua0_600_22x = "ua0-600-22x"  # JAASCois
    ua0_600_23x = "ua0-600-23x"  # PMAFind
    ua0_600_25x = "ua0-600-25x"  # Webtrends
    ua0_600_26x = "ua0-600-26x"  # Nsauditor
    ua0_600_27x = "ua0-600-27x"  # Paros
    ua0_600_28x = "ua0-600-28x"  # DirBuster
    ua0_600_29x = "ua0-600-29x"  # Pangolin
    ua0_600_2xx = "ua0-600-2xx"  # Qualys
    ua0_600_30x = "ua0-600-30x"  # SQLNinja
    ua0_600_31x = "ua0-600-31x"  # Nikto
    ua0_600_32x = "ua0-600-32x"  # WebInspect
    ua0_600_33x = "ua0-600-33x"  # BlackWidow
    ua0_600_34x = "ua0-600-34x"  # Grendel-Scan
    ua0_600_35x = "ua0-600-35x"  # Havij
    ua0_600_36x = "ua0-600-36x"  # w3af
    ua0_600_37x = "ua0-600-37x"  # Nmap
    ua0_600_39x = "ua0-600-39x"  # Nessus Scripted
    ua0_600_3xx = "ua0-600-3xx"  # Evil Scanner
    ua0_600_40x = "ua0-600-40x"  # WebFuck
    ua0_600_42x = "ua0-600-42x"  # OpenVAS
    ua0_600_43x = "ua0-600-43x"  # Spider-Pig
    ua0_600_44x = "ua0-600-44x"  # Zgrab
    ua0_600_45x = "ua0-600-45x"  # Zmeu
    ua0_600_46x = "ua0-600-46x"  # Crowdstrike
    ua0_600_47x = "ua0-600-47x"  # GoogleSecurityScanner
    ua0_600_48x = "ua0-600-48x"  # Commix
    ua0_600_49x = "ua0-600-49x"  # Gobuster
    ua0_600_4xx = "ua0-600-4xx"  # CGIchk
    ua0_600_51x = "ua0-600-51x"  # FFUF
    ua0_600_52x = "ua0-600-52x"  # Nuclei
    ua0_600_53x = "ua0-600-53x"  # Tsunami
    ua0_600_54x = "ua0-600-54x"  # Nimbostratus
    ua0_600_55x = "ua0-600-55x"  # Datadog test scanner: user-agent
    ua0_600_5xx = "ua0-600-5xx"  # Blind SQL Injection Brute Forcer
    ua0_600_6xx = "ua0-600-6xx"  # Suspicious user agent
    ua0_600_7xx = "ua0-600-7xx"  # SQLmap
    ua0_600_9xx = "ua0-600-9xx"  # Skipfish


class http_protocol_violation(StrEnum):
    crs_920_260 = "crs-920-260"  # Unicode Full/Half Width Abuse Attack Attempt
    crs_921_110 = "crs-921-110"  # HTTP Request Smuggling Attack
    crs_921_140 = "crs-921-140"  # HTTP Header Injection Attack via headers
    crs_921_160 = "crs-921-160"  # HTTP Header Injection Attack via payload (CR/LF and header-name detected)
    crs_943_100 = "crs-943-100"  # Possible Session Fixation Attack: Setting Cookie Values in HTML


class lfi(StrEnum):
    crs_930_100 = "crs-930-100"  # Obfuscated Path Traversal Attack (/../)
    crs_930_110 = "crs-930-110"  # Simple Path Traversal Attack (/../)
    crs_930_120 = "crs-930-120"  # OS File Access Attempt


class rfi(StrEnum):
    crs_931_110 = "crs-931-110"  # RFI: Common RFI Vulnerable Parameter Name used w/ URL Payload
    crs_931_120 = "crs-931-120"  # RFI: URL Payload Used w/Trailing Question Mark Character (?)


class command_injection(StrEnum):
    crs_932_160 = "crs-932-160"  # Remote Command Execution: Unix Shell Code Found
    crs_932_171 = "crs-932-171"  # Remote Command Execution: Shellshock (CVE-2014-6271)
    crs_932_180 = "crs-932-180"  # Restricted File Upload Attempt
    sqr_000_008 = "sqr-000-008"  # Windows: Detect attempts to exfiltrate .ini files
    sqr_000_009 = "sqr-000-009"  # Linux: Detect attempts to exfiltrate passwd files
    sqr_000_010 = "sqr-000-010"  # Windows: Detect attempts to timeout a shell


class unrestricted_file_upload(StrEnum):
    crs_933_111 = "crs-933-111"  # PHP Injection Attack: PHP Script File Upload Found


class php_code_injection(StrEnum):
    crs_933_130 = "crs-933-130"  # PHP Injection Attack: Global Variables Found
    crs_933_131 = "crs-933-131"  # PHP Injection Attack: HTTP Headers Values Found
    crs_933_140 = "crs-933-140"  # PHP Injection Attack: I/O Stream Found
    crs_933_150 = "crs-933-150"  # PHP Injection Attack: High-Risk PHP Function Name Found
    crs_933_160 = "crs-933-160"  # PHP Injection Attack: High-Risk PHP Function Call Found
    crs_933_170 = "crs-933-170"  # PHP Injection Attack: Serialized Object Injection
    crs_933_200 = "crs-933-200"  # PHP Injection Attack: Wrapper scheme detected


class js_code_injection(StrEnum):
    crs_934_100 = "crs-934-100"  # Node.js Injection Attack
    dog_000_005 = "dog-000-005"  # Node.js: Prototype pollution through __proto__
    dog_000_006 = "dog-000-006"  # Node.js: Prototype pollution through constructor.prototype
    sqr_000_002 = "sqr-000-002"  # Server-side Javascript injection: Try to detect obvious JS injection


class xss(StrEnum):
    crs_941_100 = "crs-941-100"  # XSS Attack Detected via libinjection
    crs_941_110 = "crs-941-110"  # XSS Filter - Category 1: Script Tag Vector
    crs_941_120 = "crs-941-120"  # XSS Filter - Category 2: Event Handler Vector
    crs_941_140 = "crs-941-140"  # XSS Filter - Category 4: Javascript URI Vector
    crs_941_180 = "crs-941-180"  # Node-Validator Deny List Keywords
    crs_941_200 = "crs-941-200"  # IE XSS Filters - Attack Detected via vmlframe tag
    crs_941_210 = "crs-941-210"  # IE XSS Filters - Obfuscated Attack Detected via javascript injection
    crs_941_220 = "crs-941-220"  # IE XSS Filters - Obfuscated Attack Detected via vbscript injection
    crs_941_230 = "crs-941-230"  # IE XSS Filters - Attack Detected via embed tag
    crs_941_240 = "crs-941-240"  # IE XSS Filters - Attack Detected via import tag
    crs_941_270 = "crs-941-270"  # IE XSS Filters - Attack Detected via link tag
    crs_941_280 = "crs-941-280"  # IE XSS Filters - Attack Detected via base tag
    crs_941_290 = "crs-941-290"  # IE XSS Filters - Attack Detected via applet tag
    crs_941_300 = "crs-941-300"  # IE XSS Filters - Attack Detected via object tag
    crs_941_350 = "crs-941-350"  # UTF-7 Encoding IE XSS - Attack Detected
    crs_941_360 = "crs-941-360"  # JSFuck / Hieroglyphy obfuscation detected


class sql_injection(StrEnum):
    crs_942_100 = "crs-942-100"  # SQL Injection Attack Detected via libinjection
    crs_942_160 = "crs-942-160"  # Detects blind sqli tests using sleep() or benchmark()
    crs_942_190 = "crs-942-190"  # Detects MSSQL code execution and information gathering attempts
    crs_942_240 = "crs-942-240"  # Detects MySQL charset switch and MSSQL DoS attempts
    crs_942_250 = "crs-942-250"  # Detects MATCH AGAINST, MERGE and EXECUTE IMMEDIATE injections
    crs_942_270 = "crs-942-270"  # Basic SQL injection
    crs_942_280 = "crs-942-280"  # SQL Injection with delay functions
    crs_942_360 = "crs-942-360"  # Detects concatenated basic SQL injection and SQLLFI attempts
    crs_942_500 = "crs-942-500"  # MySQL in-line comment detected


class nosql_injection(StrEnum):
    crs_942_290 = "crs-942-290"  # Finds basic MongoDB SQL injection attempts
    dog_000_001 = "dog-000-001"  # Look for Cassandra injections
    sqr_000_007 = "sqr-000-007"  # NoSQL: Detect common exploitation strategy


class java_code_injection(StrEnum):
    crs_944_100 = "crs-944-100"  # Remote Command Execution: Suspicious Java class detected
    crs_944_110 = "crs-944-110"  # Remote Command Execution: Java process spawn (CVE-2017-9805)
    crs_944_130 = "crs-944-130"  # Suspicious Java class detected
    dog_000_002 = "dog-000-002"  # OGNL - Look for formatting injection patterns
    dog_000_003 = "dog-000-003"  # OGNL - Detect OGNL exploitation primitives


class exploit_detection(StrEnum):
    dog_000_004 = "dog-000-004"  # Spring4Shell - Attempts to exploit the Spring4shell vulnerability
    sqr_000_017 = "sqr-000-017"  # Log4shell: Attempt to exploit log4j CVE-2021-44228


class ssrf(StrEnum):
    sqr_000_001 = "sqr-000-001"  # SSRF: Try to access the credential manager of the main cloud services
    sqr_000_011 = "sqr-000-011"  # SSRF: Try to access internal OMI service (CVE-2021-38647)
    sqr_000_012 = "sqr-000-012"  # SSRF: Detect SSRF attempt on internal service
    sqr_000_013 = "sqr-000-013"  # SSRF: Detect SSRF attempts using IPv6 or octal/hexdecimal obfuscation
    sqr_000_014 = "sqr-000-014"  # SSRF: Detect SSRF domain redirection bypass
    sqr_000_015 = "sqr-000-015"  # SSRF: Detect SSRF attempt using non HTTP protocol
