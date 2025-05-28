## Change Log

All notable changes to this project will be documented in this file.

### 2025-04 (137 PR merged)

* 2025-04-22 [Add an option to exclude some scenarios in system-tests.yml](https://github.com/DataDog/system-tests/pull/4546) by @cbeauchesne
* 2025-04-04 [Introduce a way to add extra argument to library cmd on parametric scenario](https://github.com/DataDog/system-tests/pull/4470) by @cbeauchesne


### 2025-03 (175 PR merged)

* 2025-03-28 [Add core dump on PHP weblogs](https://github.com/DataDog/system-tests/pull/4411) by @cbeauchesne
* 2025-03-24 [Create cpp_nginx library](https://github.com/DataDog/system-tests/pull/4371) by @cbeauchesne
* 2025-03-20 [onboarding: force the apm instrumentation after install the installer.](https://github.com/DataDog/system-tests/pull/4350) by @robertomonteromiguel
* 2025-03-30 [retry npm install when it fails](https://github.com/DataDog/system-tests/pull/4334) by @rochdev
* 2025-03-18 [Add library cpp_httpd](https://github.com/DataDog/system-tests/pull/4328) by @cbeauchesne
* 2025-03-18 [Allow manifest to declare skips on entire folder](https://github.com/DataDog/system-tests/pull/4325) by @cbeauchesne
* 2025-03-19 [Add order checking to format.sh](https://github.com/DataDog/system-tests/pull/4320) by @bm1549
* 2025-03-10 [support for TARGET_BRANCH load_binary.sh golang](https://github.com/DataDog/system-tests/pull/4236) by @eliottness
* 2025-03-12 [Add parallel mode in CI #4035](https://github.com/DataDog/system-tests/pull/4158) by @cbeauchesne
* 2025-03-04 [Onboarding: gitlab ci](https://github.com/DataDog/system-tests/pull/4132) by @robertomonteromiguel


### 2025-02 (236 PR merged)

* 2025-02-12 [Add yamlfmt + yamllint](https://github.com/DataDog/system-tests/pull/4077) by @bm1549
* 2025-02-10 Green CI policy by @cbeauchesne
* 2025-02-04 [Extend mypy to full project](https://github.com/DataDog/system-tests/pull/3963) by @cbeauchesned
* SSI:
  * Implement retry policies on Gitlab pipeline with the aim of reducing flakiness
  * Improvements in exception handling and messages displayed to the end user
  * Enable all new vm distros and report to feature parity dashboard

### 2025-01 (179 PR merged)

* 2025-01-20 [Deserialize JSON in multipart](https://github.com/DataDog/system-tests/pull/3854) by @cbeauchesne
* 2025-01-14 [[python] add new python weblog: django-py3.13](https://github.com/DataDog/system-tests/pull/3798) by @christophe-papazian
* 2025-01-09 [Removes CircleCI job](https://github.com/DataDog/system-tests/pull/3792) by @cbeauchesne
* 2025-01-03 [Add an option that skip all tests if scenario contains only xfail/skip](https://github.com/DataDog/system-tests/pull/3768) by @cbeauchesne
* 2025-01-27 [Try to get TARGET_BRANCH from PR's title](https://github.com/DataDog/system-tests/pull/3675) by @iunanua
* 2025-01-30 [[golang] new orchestrion go weblog](https://github.com/DataDog/system-tests/pull/3555) by @eliottness
* 2025-01-16 [Add tests for Service Extension (Envoy External Processing)](https://github.com/DataDog/system-tests/pull/3377) by @e-n-0

### 2024-12 (138 PR merged)

* 2024-12-31 [Allow a class to declare several scenarios](https://github.com/DataDog/system-tests/pull/3757) by @cbeauchesne
* 2024-12-17 Optimization of java weblogs [1](https://github.com/DataDog/system-tests/pull/3701), [2](https://github.com/DataDog/system-tests/pull/3697), [3](https://github.com/DataDog/system-tests/pull/3694) and [4](https://github.com/DataDog/system-tests/pull/3693) by @smola
* 2024-12-13 Use ruff instead of black as [formatter](https://github.com/DataDog/system-tests/pull/3656) and [linter](https://github.com/DataDog/system-tests/pull/3631) by @cbeauchesne
* 2024-12-03 Lot ofrevamp of k8 tests by @robertomonteromiguel

### 2024-11 (207 PR merged)

* 2024-11-22 [Docker SSI: report data to FPD](https://github.com/DataDog/system-tests/pull/3525) by @robertomonteromiguel
* 2024-11-21 [adding mypy checks](https://github.com/DataDog/system-tests/pull/3488) by @rachelyangdog
* 2024-11-18 [[ruby] Add Rails 7.2 and Rails 8.0 weblogs](https://github.com/DataDog/system-tests/pull/3471) by @vpellan
* 2024-11-13 [Use a unique way to define scenario groups #3400](https://github.com/DataDog/system-tests/pull/3451) by @cbeauchesne
* 2024-11-18 [Test for zombie processes in crashtracking](https://github.com/DataDog/system-tests/pull/3364) by @kevingosse
* 2024-11-04 [Fix parametric instability at container start](https://github.com/DataDog/system-tests/pull/3359) by @cbeauchesne
* 2024-11-06 [parametric: Adds a feature to track the parity for parametric endpoints](https://github.com/DataDog/system-tests/pull/3345) by @mabdinur
* 2024-11-04 [[golang] Migrate Parametric app from grpc to http](https://github.com/DataDog/system-tests/pull/3332) by @mtoffl01


### 2024-10 (176 PR merged)

* Lot of work done on SSI/onboarding by @robertomonteromiguel and @emmettbutler
* 2024-10-24 [[Ruby] Convert parametric implementation from grpc to http](https://github.com/DataDog/system-tests/pull/3279) by @ZStriker19 and @marcotc
* 2024-10-17 [Onboarding: feature parity dashboard](https://github.com/DataDog/system-tests/pull/3247) by @robertomonteromiguel
* 2024-10-08 [Proxy exports files content in a separated folder in logs](https://github.com/DataDog/system-tests/pull/3179) by @cbeauchesne
* 2024-10-07 [External processing : initial poc](https://github.com/DataDog/system-tests/pull/3097) by @cbeauchesne and @e-n-0

### 2024-09 (157 PR merged)

* 2024-09-23 [Remove legacy check on python 3.9](https://github.com/DataDog/system-tests/pull/3094) by @cbeauchesne
* 2024-09-18 [Enforce JIRA ticket in bug/flaky declarations](https://github.com/DataDog/system-tests/pull/3034) by @cbeauchesne
* 2024-09-12 [[ruby] Increment path in ruby "dev" version, and set a prerelease](https://github.com/DataDog/system-tests/pull/3022) by @cbeauchesne
* 2024-09-12 [Removes system-tests-core form owners of manifests](https://github.com/DataDog/system-tests/pull/3018) by @cbeauchesne
* 2024-09-06 [`-o xfail_strict=True` to force XPASS to fail](https://github.com/DataDog/system-tests/pull/2995) by @cbeauchesne
* 2024-09-10 [Print weblog crash logs](https://github.com/DataDog/system-tests/pull/2912) by @simon-id


### 2024-08 (102 PR merged)

* 2024-08-29 [[java] Enable e2e tests on all spring-boot variants](https://github.com/DataDog/system-tests/pull/2946) by @smola
* 2024-08-22 [[java] Use HTTP interface for parametric test](https://github.com/DataDog/system-tests/pull/2869) by @cbeauchesne
* 2024-08-05 [parametric: adds a consistent interface for retrieving traces and spans](https://github.com/DataDog/system-tests/pull/2789) by @mabdinur
* 2024-08-05 [[nodejs] allow mounting local dd-trace-js as weblog volume](https://github.com/DataDog/system-tests/pull/2777) by @rochdev


### 2024-07 (166 PR merged)

* 2024-07-22 [Ability to change the support state of meta struct of the agent](https://github.com/DataDog/system-tests/pull/2770) by @e-n-0
* 2024-07-18 [Add better support for the new RC API](https://github.com/DataDog/system-tests/pull/2757) by @christophe-papazian
* 2024-07-23 [Start containers in parallel](https://github.com/DataDog/system-tests/pull/2732) by @rochdev
* 2024-07-10 [New Remote Config testing API](https://github.com/DataDog/system-tests/pull/2719) by @cbeauchesne
* 2024-07-02 [OnBoarding: Host and container guardrail testing](https://github.com/DataDog/system-tests/pull/2647) by @robertomonteromiguel


### 2024-06 (92 PR merged)

* 2024-06-26 [add pytest-split to allow splitting test running in groups](https://github.com/DataDog/system-tests/pull/2589) by @rochdev
* 2024-06-24 [Remote config test API](https://github.com/DataDog/system-tests/pull/2586) by @cbeauchesne
* 2024-06-20 [[golang] Enable RASP SSRF tests](https://github.com/DataDog/system-tests/pull/2576) by @eliottness
* 2024-06-24 [RASP SQLi: enhance test & activate for Go](https://github.com/DataDog/system-tests/pull/2574) by @Hellzy
* 2024-06-19 [[go] implement RASP endpoints](https://github.com/DataDog/system-tests/pull/2551) by @eliottness
* 2024-06-03 [[python] RASP sqli tests for python](https://github.com/DataDog/system-tests/pull/2514) by @christophe-papazian


### 2024-05 (90 PR merged)

* 2024-05-27 [Use semver for version parser](https://github.com/DataDog/system-tests/pull/2487) by @cbeauchesne
* 2024-05-07 [[python] decrease the waiting time for python libraries from 25s to 5s](https://github.com/DataDog/system-tests/pull/2431) by @christophe-papazian
* 2024-05-29 [Manifest references + Node.js semver migration](https://github.com/DataDog/system-tests/pull/2416) by @simon-id
* 2024-05-03 [Dynamically compute scenarios to run](https://github.com/DataDog/system-tests/pull/2408) by @cbeauchesne


### 2024-04 (104 PR merged)

* 2024-04-18 [Compute dynamically the matrix to run in CI](https://github.com/DataDog/system-tests/pull/2356) by @cbeauchesne
* 2024-04-18 [Build docker images if there is a label](https://github.com/DataDog/system-tests/pull/2321) by @robertomonteromiguel
* 2024-04-03 [K8s lib injection: new python variants](https://github.com/DataDog/system-tests/pull/2293) by @robertomonteromiguel
* 2024-04-25 [Support semver version ranges for `released` decorator (and manifests)](https://github.com/DataDog/system-tests/pull/2045) by @simon-id


### 2024-03 (85 PR merged)

* 2024-03-27 [Add more ruby variants](https://github.com/DataDog/system-tests/pull/2246) by @lloeki
* 2024-03-20 [New Ruby variant : Rails 7.1](https://github.com/DataDog/system-tests/pull/2242) by @lloeki
* 2024-03-18 [Add OTel Interoperability System tests](https://github.com/DataDog/system-tests/pull/2128) by @PROFeNoM


### 2024-02 (73 PR merged)

* 2024-02-15 [Allow the main workflow to be called in a distant workflow](https://github.com/DataDog/system-tests/pull/2150) by @cbeauchesne
* 2024-02-16 [Conti/add aws kinesis tests](https://github.com/DataDog/system-tests/pull/2143) by @wconti27
* 2024-02-15 [feat: add aws sns context propagation and DSM tests](https://github.com/DataDog/system-tests/pull/2095) by @wconti27
* 2024-02-01 [OnBoarding: new tests for args block list](https://github.com/DataDog/system-tests/pull/2089) by @robertomonteromiguel
* 2024-02-01 [feat: add rabbitmq sample apps](https://github.com/DataDog/system-tests/pull/2066) by @wconti27
* 2024-02-13 [Graphql blocking tests](https://github.com/DataDog/system-tests/pull/1879) by @uurien


### 2024-01 (86 PR merged)

* 2024-01-29 [Check variant names in manifest validation](https://github.com/DataDog/system-tests/pull/2082) by @cbeauchesne
* 2024-01-29 [Generate buddies on merge if needed](https://github.com/DataDog/system-tests/pull/2068) by @robertomonteromiguel
* 2024-01-15 [Support for PHP unified client library](https://github.com/DataDog/system-tests/pull/1998) by @robertomonteromiguel
* 2024-01-08 Parametric: test "dev" version of clienty libraries by @robertomonteromiguel
* 2024-01-04 [parametric: test C++ client library](https://github.com/DataDog/system-tests/pull/1942) by @dmehala

### December 2023 (75 PR merged)

* 2023-12-27 Declare lot of features ID ([1](https://github.com/DataDog/system-tests/pull/1968), [2](https://github.com/DataDog/system-tests/pull/1952), [3](https://github.com/DataDog/system-tests/pull/1967), [4](https://github.com/DataDog/system-tests/pull/1928), [5](https://github.com/DataDog/system-tests/pull/1915), [6](https://github.com/DataDog/system-tests/pull/1910), [7](https://github.com/DataDog/system-tests/pull/1901)) by @cbeauchesne
* 2023-12-01 [Add "features" decorator](https://github.com/DataDog/system-tests/pull/1883), and [ensure in CI that all tests has a features decorator](https://github.com/DataDog/system-tests/pull/1923) by @cbeauchesne
* 2023-12-27 Parametric: allow to test dev version for [python](https://github.com/DataDog/system-tests/pull/1959), [java](https://github.com/DataDog/system-tests/pull/1937), [nodejs](https://github.com/DataDog/system-tests/pull/1941) and [golang](https://github.com/DataDog/system-tests/pull/1948) by @robertomonteromiguel

### November 2023 (78 PR merged)

* 2023-11-23 [[PHP] Support unified package](https://github.com/DataDog/system-tests/pull/1862) by @Anilm3
* 2023-11-07 [Sleep mode for all scenarios](https://github.com/DataDog/system-tests/pull/1794) by @robertomonteromiguel
* 2023-11-07 [[Tracing] Add endpoints to Python Weblog application related to Kafka Producer and Consumer calls](https://github.com/DataDog/system-tests/pull/1783) by @wantsui

### October 2023 (100 PR merged)

* 2023-10-09 [New python/FastAPI variant](https://github.com/DataDog/system-tests/pull/1663) by @christophe-papazian
* 2023-10-27 [New Node.js/NextJS variant](https://github.com/DataDog/system-tests/pull/1662) by @uurien
* 2023-10-01 [New scenario for testing debugger probes](https://github.com/DataDog/system-tests/pull/1632) by @shurivich

### September 2023 (84 PR merged)

* 2023-09-25 [New weblog variant: testing new Python version 3.12](https://github.com/DataDog/system-tests/pull/1617)
* 2023-09-22 [DB Integrations scenario: validate DB query reporting](https://github.com/DataDog/system-tests/pull/1601)
* 2023-09-20 [Parametric tests can use version in decorator/manifest file](https://github.com/DataDog/system-tests/pull/1589)
* 2023-09-08 [Agent version can be used in decorators and manifest file](https://github.com/DataDog/system-tests/pull/1577)
* 2023-09-08 [DB Integrations scenario: validate DB query reporting](https://github.com/DataDog/system-tests/pull/1410)
* All the month: lot of PR to migrate all `released` decorators to manifest files :tada:

### August 2023 (71 PR merged)

* 2023-08-31 [Deserilize appsec tags in deserializer](https://github.com/DataDog/system-tests/pull/1543) ASM data are visible as plain JSON in logs
* 2023-08-18 [Add stdout interface for postgres DB container](https://github.com/DataDog/system-tests/pull/1496) Ability to make assertion on DB containers (like Postgres) logs
* 2023-08-14 [Add pylint](https://github.com/DataDog/system-tests/pull/1486) Code quality for system-tests internales
* 2023-08-16 [Implementation of manifest files](https://github.com/DataDog/system-tests/pull/1481) :tada:


### July 2023 (86 PR merged)

* 2023-07-31 [Add library version detection for parametric tests](https://github.com/DataDog/system-tests/pull/1442) Parametric tests can now use `@released`
* 2023-07-19 [Merge parametric CI inside main CI](https://github.com/DataDog/system-tests/pull/1415) Lot of simplifications in system tests CI
* 2023-07-21 [RFC: manifest file](https://github.com/DataDog/system-tests/pull/1338) Manifest file RFC is validated !
* 2023-07-04 [Live Debugger test scenarios](https://github.com/DataDog/system-tests/pull/1296) New scenario for live debugger features


### June 2023 (77 PR merged)

* 2023-06-12 [VsCode configuration files](https://github.com/DataDog/system-tests/pull/1244): Run and debug your test
* 2023-06-16 [Force a test execution](https://github.com/DataDog/system-tests/pull/1270): Temporary force a test to be executed in your CI ([doc](https://github.com/DataDog/system-tests/blob/main/docs/execute/force-execute.md))
* 2023-06-22 [Migrate parametric tests](https://github.com/DataDog/system-tests/pull/1279): Parametric tests are now a regular scenario of system tests
* 2023-06-07 [New onboarding tests](https://github.com/DataDog/system-tests/pull/1191): Test the APM onboarding experience for customers using lib injection ([doc](https://github.com/DataDog/system-tests/tree/main/tests/onboarding))
* 2023-06-26 [New java weblog: spring-boot-payara](https://github.com/DataDog/system-tests/pull/1287)
* Some performance improvements on build step.


### May 2023 (65 PR merged)

* 2023-05-30 [Each tracer team is owner of its weblog variants](https://github.com/DataDog/system-tests/pull/1216) by @smola
* 2023-05-23 [New java weblog : akka-http](https://github.com/DataDog/system-tests/pull/1064) by @cataphract
* 2023-05-16 [Replay mode :tada:](https://github.com/DataDog/system-tests/pull/1169) by @cbeauchesne
* 2023-05-09 [Ability to run a set of scenario](https://github.com/DataDog/system-tests/pull/1133) by @cbeauchesne
* 2023-05-02 [New java weblog : Vert.x 4.x](https://github.com/DataDog/system-tests/pull/1012) by @manuel-alvarez-alvarez


### April 2023 (85 PR merged)

* 2023-04-28 [Show requests/response in log on failure ](https://github.com/DataDog/system-tests/pull/1128) by @cbeauchesne
* 2023-04-27 [Allow to specify an arbitrary test file in a non-default scenario](https://github.com/DataDog/system-tests/pull/1124) by @cbeauchesne
* 2023-04-25 [Add opentelemetry intake end-to-end system tests](https://github.com/DataDog/system-tests/pull/976) by @songy23
* 2023-04-25 [new onboarding tests](https://github.com/DataDog/system-tests/pull/930) by @robertomonteromiguel
* 2023-04-25 [Update CODEOWNERS : Add @DataDog/appsec-libraries to owmers of tests/appsec folder ](https://github.com/DataDog/system-tests/pull/1090) by @cbeauchesne
* 2023-04-19 [Runner is now in executed on host](https://github.com/DataDog/system-tests/pull/958) by @cbeauchesne
* 2023-04-13 [Add Vert.x support for java IAST](https://github.com/DataDog/system-tests/pull/969) by @manuel-alvarez-alvarez

### March 2023 (76 PR merged)

* ...

### February 2023 (74 PR merged)

* ...
