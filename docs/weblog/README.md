# Weblog

A weblog is a web app that system uses to test the library. It mimics what would be a real instrumented HTTP application. A weblog app is required for each platform that the system tests will test. The weblog must implement a number of different endpoints.

> Note: a separate document describes [GraphQL Weblog](./graphql_weblog.md).

## Disclaimer

This document describes endpoints implemented on weblog. Though, it's not a complete description, and can contains mistakes. The source of truth are the test itself. If a weblog endpoint passes system tests, then you can consider it as ok. And if it does not passes it, then you must correct it, even if it's in line with this document.

**You are strongly encouraged to help others by submitting corrections when you notice issues with this document.**

## Endpoints

All these endpoints must respond `200` unless noted otherwise. If content is not specified, it means that it is not tested. But for coherence, the most used content should be documented.

### \[GET, POST\] /

The following text may be written to the body of the response:

```
Hello world!\n
```

### GET /headers

This endpoint must set the following headers:

```
content-type: text
content-length: 16
content-language: en-US
```

Note: The content length must be present, whatever the value as long as it's numeric.

The following text may be written to the body of the response:

```
Hello headers!\n
```

### GET /identify

This endpoint must set the following tags on the local root span:

```
usr.id
usr.email
usr.name
usr.session_id
usr.role
usr.scope
```

The value of each tag should be the tag name, for example `usr.id` should be set to `usr.id`.

### GET /identify-propagate

This endpoint must set the following tags on the local root span:

```
_dd.p.usr_id
```

The value of `_dd.p.usr.id` should be `dXNyLmlk`, which is the base64 encoding of `usr.id`.

### GET /params/%s

This endpoint must accept a parameter that is a string and is part of the URL path.

The following text may be written to the body of the response:

```
Hello world!\n
```

### GET /sample_rate_route/%i

This endpoint must accpect a parameter `i` as an integer.

The following text may be written to the body of the response:

```
Hello world!\n
```

### GET /spans

The endpoint may accept two query string parameters:

* `repeats` - this is the number of spans that should be manually created (default `1`). Span must be flatten (not nested)
* `garbage` - this is the number of tags that should added to each a span (default `1`). Tag must be of the form `garbage{i}: Random string`, `i` starting at `0`

The following text should be written to the body of the response:

```
Generated {repeats} spans with {garbage} garbage tags\n
```

Where `repeats` and `garbage` are the parameters read from the query string.

### GET /sqli

The endpoint must accept a query string parameter `q`. This parameter should be used as part of a query that is executed against a real database (to ensure a database span is created).

The output of the query should be written to the body of the response.

### `GET /status`

The endpoint must accept a query string parameter `code`, which should be an integer. This parameter will be the status code of the response message.

### \[All HTTP verbs\] /waf

This is a generic endpoint. It must accept all methods, all content types, all queries and all sub paths, including empty ones.

The following text should be written to the body of the response:

```
Hello world!\n
```

In particular, it accepts and parse JSON and XML content. A typical XML content is :

```xml
<?xml version='1.0' encoding='utf-8'?>
<string attack="attr">
    content
</string>
```

### \[GET, POST, OPTIONS\] /tag_value/:tag_value/:status_code

This endpoint must accept two required parameters (the first is a string, the second is an integer) and are part of the URL path.

Make sure the parameters are name :tag_value and :status_code. Those values are use for the test in tests/appsec/api_security/test_schemas.py

This endpoint must accept all query parameters and all content types.

The first path parameter must be written in the span with the tag `appsec.events.system_tests_appsec_event.value` and the parameter as value.

The second path parameter must be used as a response status code.

All query parameters (key, value) must be used as (key, value) in the response headers.

The response for this endpoint must be:

```
Value tagged
```

**There is one exception**

The exception was introduced for testing API Security response body

If the first string parameter (:tag_value) starts with `payload_in_response_body` and the method is `POST`.

Then the response should contain json with the format:

```
{"payload": payload}
```

where payload is the parsed body of the request


Make sure to specify the Content-Type header as `application/json`

#### Example

```
/tag_value/tainted_value/418?Content-Language=fr&custom_field=myvalue
```
must set the appropriate tag in the span to `tainted_value` and return a response with the teapot code with reponse headers populated with `Content-Language=fr` and `custom_field=myvalue`.

The goal is to be able to easily test if a request was blocked before reaching the server code or after by looking at the span and also test security rules on reponse status code or response header content.

### GET /iast/insecure_hashing/deduplicate

Parameterless endpoint. This endpoint contains a vulnerable souce code line (weak hash) in a loop with at least two iterations.

### GET /iast/insecure_hashing/multiple_hash

Parameterless endpoint. This endpoint contains 2 different insecure hashing operations (for example md5 and sha1). These operations are located in differents points of the executed source code.

### GET /iast/insecure_hashing/test_secure_algorithm

The endpoint executes a unique operation of String hashing with secure SHA-256 algorithm

The endpoint executes a unique operation of String hashing with given algorithm name

### GET /iast/insecure_hashing/test_md5_algorithm

The endpoint executes a unique operation of String hashing with unsecure MD5 algorithm

### GET /iast/hardcoded_secrets/test_insecure

Parameterless endpoint. This endpoint contains a hardcoded secret. The declaration of the hardcoded secret should be sufficient to trigger the vulnerability, so returning it in the response is optional.

### \[GET, POST\] /iast/source/*

This group of endpoints should trigger vulnerabilities detected by IAST with untrusted data coming from certain sources. The used vulnerability is irrelevant. It could be a command injection, SQL injection, or something else.

**Warning:** Note that each of these endpoints should trigger the vulnerability at a different line in the source code, otherwise, vulnerabilities will be deduplicated. So be careful with refactors.

#### GET /iast/source/parameter/test

A GET request using a `table` query parameter with any value. For example, `?table=users`.

#### POST /iast/source/parameter/test

A POST request using `table` as a form parameter with any value.

#### GET /iast/source/parametername/test

A GET request using `table` query parameter name, with any value. The test should retrieve the name itself (without it being hardcoded), and use the name, rather than the value.

#### POST /iast/source/parametername/test

A POST request using `user` form parameter name. See the GET-variant for the implementation.

#### GET /iast/source/header/test

A GET request using a header `table` with any value.

#### GET /iast/source/headername/test

A GET request using a header `table` with any value. It will use its name, without it being harded.

#### GET /iast/source/cookievalue/test

A GET request using a cookie with name `table` and any value. The value must be used in the vulnerability.

#### GET /iast/source/cookiename/test

A GET request using a cookie with name `table` and any value. The name must be used in the vulnerability.

#### POST /iast/source/multipart/test
A multipart request uploading a file (with a file name).

#### POST /iast/source/body/test

A POST request which will receive the following JSON body:

```
{"name": "table", "value": "user"}
```

Where the value for `value` must be used in the vulnerability.

### GET /make_distant_call

This endpoint accept a mandatory parameter `url`. It'll make a call to these url, and should returns a JSON response :

```json
{
    "url": <url in paramter>,
    "status_code": <status code of the response>,
    "request_headers": <request headers as a dict>,
    "response_headers": <response headers as a dict>,
}
```

### GET /dbm

This endpoint executes database queries for [DBM supported libraries](https://docs.datadoghq.com/database_monitoring/guide/connect_dbm_and_apm/?tab=go#before-you-begin). A 200 response is returned if the query
is executed successfully.

Expected SQL query:
- For SqlServer: `SELECT @@version`
- For PostgreSQL & MySQL: `SELECT version()`

Expected query params:
  - `integration`: Name of DBM supported library
    - Possible Values: `psycopg`
  - `operation`: Method used to execute database statements
    - Possible Values: `execute`, `executemany`


Supported Libraries:
  - Python:
    - [pyscopg](https://www.psycopg.org/docs/index.html) (Python PostgreSQL adapter)
  - .NET:
    - [npgsql](https://www.nuget.org/packages/npgsql) (ADO.NET Data Provider for PostgreSQL)
    - [mysql](https://www.nuget.org/packages/MySql.Data) (ADO.NET driver for MySQL)
  - PHP:
    - [pdo](https://www.php.net/manual/en/book.pdo.php) (Data Objects for accessing multiple databases)
    - [mysqli](https://www.php.net/manual/en/book.mysqli.php) (Extension that interacts with MySQL)

### GET /dsm

This endpoint executes database queries for DSM supported libraries. A 200 response with message "ok" is returned
if the produce and consume calls for the specified tech are started successfully. Otherwise, error messages will
be returned.

Expected query params:
  - `integration`: Name of messaging tech
    - Possible Values: `kafka`, `rabbitmq`, `sqs`

### GET /user_login_success_event

This endpoint calls the appsec event tracking SDK function used for user login success.

By default, the generated event has the following specification:
- User ID: `system_tests_user`
- Metadata: `{metadata0: value0, metadata1: value1}`

Values can be changed with the query params called `event_user_id`.

### GET /user_login_failure_event

This endpoint calls the appsec event tracking SDK function used for user login failure.

By default, the generated event has the following specification:
- User ID: `system_tests_user`
- Exists: `true`
- Metadata: `{metadata0: value0, metadata1: value1}`

Values can be changed with the query params called `event_user_id` and `event_user_exists`.

### GET /custom_event

This endpoint calls the appsec event tracking SDK function used for custom events.

By default, the generated event has the following specification:
- Event name: `system_tests_event`
- Metadata: `{metadata0: value0, metadata1: value1}`

Values can be changed with the query params called `event_name`.

### GET /users

This endpoint calls the appsec blocking SDK functions used for blocking users. If the expected parameter matches one of
the possible values the WAF will return the proper action.

Expected query parameters:
- `user`: user id.
  - Possible values: `blockedUser`

### GET /load_dependency

This endpoint loads a module/package in applicable languages. It's mainly used for telemetry tests to verify that
the `dependencies-loaded` event is appropriately triggered.

### GET /e2e_single_span

This endpoint will create two spans, a parent span (which is a root-span), and a child span.
The spans created are not sub-spans of the main root span automatically created by system-tests, but
they will have the same `user-agent` containing the request ID in order to allow assertions on them.

The following query parameters are required:
- `parentName`: The name of the parent span (root-span).
- `childName`: The name of the child span (the parent of this span is the root-span identified by `parentName`).

The following query parameters are optional:
- `shouldIndex`: Valid values are `1` and `0`. When `shouldIndex=1` is provided, special tags are added in the spans that will force their indexation in the APM backend, without explicit retention filters needed.

This endpoint is used for the Single Spans tests (`test_single_span.py`).

### GET /e2e_otel_span

This endpoint will create two spans, a parent span (which is a root-span), and a child span.
The spans created are not sub-spans of the main root span automatically created by system-tests, but
they will have the same `user-agent` containing the request ID in order to allow assertions on them.

The following query parameters are required:
- `parentName`: The name of the parent span (root-span).
- `childName`: The name of the child span (the parent of this span is the root-span identified by `parentName`).

The following query parameters are optional:
- `shouldIndex`: Valid values are `1` and `0`. When `shouldIndex=1` is provided, special tags are added in the spans that will force their indexation in the APM backend, without explicit retention filters needed.

This endpoint is used for the OTel API tests (`test_otel.py`). In the body of the endpoint, multiple properties are set on the span to verify that the API works correctly.
To read more about the specific values being used, check `test_otel.py` for up-to-date information.

### \[GET,POST\] /login
This endpoint is used to authenticate a user.
Body fields accepted in POST method:
- `username`: the login name for the user.
- `password`: password for the user.

It also supports HTTP authentication by using GET method and the authorization header.
Additionally both methods support the following query parameters to use the sdk functions along with the authentication framework:
- `sdk_event`: login event type: `success` or `failure`.
- `sdk_user`: user id to be used in the sdk call.
- `sdk_mail`: user's mail to be used in the sdk call.
- `sdk_user_exists`: `true` of `false` to indicate wether the current user exists and populate the corresponding tag.

### GET /debugger
These endpoints are used for the Live Debugger tests. Currently, they are placeholders but will eventually be used to create and test different probe definitions.

#### GET /debugger/log
This endpoint will be used to validate the log probe.

#### GET /debugger/metric
This endpoint will be used to validate the metric probe.

#### GET /debugger/span
This endpoint will be used to validate the span probe.

#### GET /debugger/span-decoration
This endpoint will be used to validate the span decoration probe.

The following query parameters are required for each endpoint:
- `arg`: This is a parameter that can take any string as an argument.
- `intArg`: This is a parameter that can take any integer as an argument.

#### GET /debugger/pii
This endpoint will be used to validate debugger pii redaction feature.

#### GET /expression
#### GET /expression/exception
These endpoints will be used to validate debugger expression language feature.

### GET /createextraservice
should rename the trace service, creating a "fake" service

The parameter `serviceName` is required and should be a string with the name for the fake service

### POST /shell_execution
This endpoint is used to spawn a new process and test that shell execution span is properly sent.
It supports the following body fields:
- `command`: the program or script to be executed.
- `options`: a record with the following options:
  - `shell`: boolean in order to instruct if the program should be executed within a shell.
- `args`: arguments passed to the program.

### GET /flush
This endpoint is OPTIONAL and not related to any test, but to the testing process. When called, it should flush any remaining data from the library to the respective outputs, usually the agent. See more in `docs/internals/flushing.md`.

### \[GET,POST\] /rasp/lfi

This endpoint is used to test for local file inclusion / path traversal attacks, consequently it must perform an operation on a file or directory, e.g. `open` with a relative path. The chosen operation must be injected with the `GET` or `POST` parameter.

Query parameters and body fields required in the `GET` and `POST` method:
- `file`: containing the string to inject on the file operation.

The endpoint should support the following content types in the `POST` method:
- `application/x-www-form-urlencoded`
- `application/xml`
- `application/json`

The chosen operation must use the file as provided, without any alterations, e.g.:
```
open($file);
```

Examples:
- `GET`: `/rasp/lfi?file=../etc/passwd`
- `POST`: `{"file": "../etc/passwd"}`

### \[GET,POST\] /rasp/ssrf

This endpoint is used to test for server side request forgery attacks, consequently it must perform a network operation, e.g. an HTTP request. The chosen operation must be partially injected with the `GET` or `POST` parameter.

Query parameters and body fields required in the `GET` and `POST` method:
- `domain`: containing the string to partially inject on the network operation.

The endpoint should support the following content types:
- `application/x-www-form-urlencoded`
- `application/xml`
- `application/json`

The url used in the network operation should be similar to the following:
```
http://$domain
```

Examples:
- `GET`: `/rasp/ssrf?domain=169.254.169.254`
- `POST`: `{"domain": "169.254.169.254"}`

### \[GET,POST\] /rasp/sqli

This endpoint is used to test for SQL injection attacks, consequently it must perform a database query. The chosen operation must be partially injected with the `GET` or `POST` parameter.

Query parameters and body fields required in the `GET` and `POST` method:
- `user_id`: containing the string to partially inject on the SQL query.

The endpoint should support the following content types:
- `application/x-www-form-urlencoded`
- `application/xml`
- `application/json`

The statement used in the query should be similar to the following:

```sql
SELECT * FROM users WHERE id='$user_id';
```

Examples:
- `GET`: `/rasp/ssrf?user_id="' OR 1 = 1 --"`
- `POST`: `{"user_id": "' OR 1 = 1 --"}`

### GET /dsm/inject
This endpoint is used to validate DSM context injection injects the correct encoding to a headers carrier.

### GET /dsm/extract
This endpoint is used to validate DSM context extraction works correctly when provided a headers carrier with the context already present within the headers.

### \[GET,POST\] /requestdownstream
This endpoint is used to test ASM Standalone propagation, by calling `/returnheaders` and returning it's value (the headers received) to inspect them, looking for
distributed tracing propagation headers.

### \[GET,POST\] /returnheaders
This endpoint returns the headers received in order to be able to assert about distributed tracing propagation headers

### GET /healthcheck

Returns a JSON dict, with those values : 

```js
{
    "status": "ok",
    "library": {
      "language": "<language>",  // one of cpp, dotnet, golang, java, nodejs, php, python, ruby
      "version": "1.2.3",  // version of the library
      "libddwaf_version": "4.5.6"  // version of libddwaf
    }
  }
```
