## Change Log

All notable changes to this project will be documented in this file.

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
