# Weblog

A weblog is a web app that system uses to test the library. It mimics what would be a real instrumented HTTP application. A weblog app is required for each platform that the system tests will test. The weblog must implement a number of different endpoints.
Weblog implementations are located in `utils/docker/`.

> Note: a separate document describes [GraphQL Weblog](./graphql_weblog.md).

## Disclaimer

This document describes endpoints implemented on weblog. Though, it's not a complete description, and can contain mistakes. The source of truth are the test itself. If a weblog endpoint passes system tests, then you can consider it as ok. And if it does not pass it, then you must correct it, even if it's in line with this document.

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

This endpoint must accept a parameter `i` as an integer.

The following text may be written to the body of the response:

```
Hello world!\n
```

### GET /api_security/sampling/%i

This endpoint is used for API security sampling and must accept a parameter `i` as an integer.

The response status code must be `i`.

The response body may contain the following text:

```
Hello!\n
```

### GET /api_security_sampling/%i

This endpoint is used in conjunction with `GET /api_security/sampling/%i` for API security sampling and must accept a parameter `i` as an integer.

The response body may contain the following text:

```
OK\n
```


### GET /spans

The endpoint may accept two query string parameters:

* `repeats` - this is the number of spans that should be manually created (default `1`). Span must be flattened (not nested)
* `garbage` - this is the number of tags that should be added to each a span (default `1`). Tag must be of the form `garbage{i}: Random string`, `i` starting at `0`

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
must set the appropriate tag in the span to `tainted_value` and return a response with the teapot code with response headers populated with `Content-Language=fr` and `custom_field=myvalue`.

The goal is to be able to easily test if a request was blocked before reaching the server code or after by looking at the span and also test security rules on response status code or response header content.

### GET /iast/insecure-cookie/test_secure

This endpoint should set at least one cookie with all security flags (Secure, HttpOnly, SameSite=Strict) to prevent any vulnerabilities from being detected.

### GET /iast/insecure-cookie/test_insecure

This endpoint should set a cookie with all security flags except Secure, to detect only the INSECURE_COOKIE vulnerability.

### POST /iast/insecure-cookie/custom_cookie

This endpoint should set a cookie with the name and value coming from the request body (using the cookieName and cookieValue properties), with all security flags except Secure, to detect only the INSECURE_COOKIE vulnerability.

### GET /iast/insecure-cookie/test_empty_cookie

This endpoint should set a cookie with empty cookie value without Secure flag, INSECURE_COOKIE vulnerability shouldn't be detected.

### GET /iast/insecure_hashing/deduplicate

Parameterless endpoint. This endpoint contains a vulnerable source code line (weak hash) in a loop with at least two iterations.

### GET /iast/insecure_hashing/multiple_hash

Parameterless endpoint. This endpoint contains 2 different insecure hashing operations (for example md5 and sha1). These operations are located in different points of the executed source code.

### GET /iast/insecure_hashing/test_secure_algorithm

The endpoint executes a unique operation of String hashing with secure SHA-256 algorithm

The endpoint executes a unique operation of String hashing with given algorithm name

### GET /iast/insecure_hashing/test_md5_algorithm

The endpoint executes a unique operation of String hashing with unsecure MD5 algorithm

### GET /iast/hardcoded_secrets/test_insecure

Parameterless endpoint. This endpoint contains a hardcoded secret. The declaration of the hardcoded secret should be sufficient to trigger the vulnerability, so returning it in the response is optional.

### GET /iast/no-httponly-cookie/test_secure

This endpoint should set at least one cookie with all security flags (Secure, HttpOnly, SameSite=Strict) to prevent any vulnerabilities from being detected.

### GET /iast/no-httponly-cookie/test_insecure

This endpoint should set a cookie with all security flags except HttpOnly, to detect only the NO_HTTPONLY_COOKIE vulnerability.

### GET /iast/no-httponly-cookie/test_empty_cookie

This endpoint should set a cookie with empty cookie value without HttpOnly flag, NO_HTTPONLY_COOKIE vulnerability shouldn't be detected.

### POST /iast/no-httponly-cookie/custom_cookie

This endpoint should set a cookie with the name and value coming from the request body (using the cookieName and cookieValue properties), with all security flags except HttpOnly, to detect only the NO_HTTPONLY_COOKIE vulnerability.

### GET /iast/no-samesite-cookie/test_secure

This endpoint should set at least one cookie with all security flags (Secure, HttpOnly, SameSite=Strict) to prevent any vulnerabilities from being detected.

### GET /iast/no-samesite-cookie/test_insecure

This endpoint should set a cookie with all security flags except SameSite=Strict, to detect only the NO_SAMESITE_COOKIE vulnerability.

### GET /iast/no-samesite-cookie/test_empty_cookie

This endpoint should set a cookie with empty cookie value without SameSite=Strict flag, NO_SAMESITE_COOKIE vulnerability shouldn't be detected.

### POST /iast/no-samesite-cookie/custom_cookie

This endpoint should set a cookie with the name and value coming from the request body (using the cookieName and cookieValue properties), with all security flags except SameSite=Strict, to detect only the NO_SAMESITE_COOKIE vulnerability.

### GET /iast/header_injection/reflected/exclusion

This endpoint should set the header whose name comes in the `reflected` field of the query string, with the reflected value of another header whose name comes in the `origin` field of the query string.

### GET /iast/header_injection/reflected/no-exclusion

Same behaviour as `/iast/header_injection/reflected/exclusion` but with separate specific cases to obtain a different vulnerability location to avoid deduplication.

### GET /iast/sampling-by-route-method-count/:key

This endpoint must contain 15 different vulnerabilities, each on a separate line of code, regardless of their type, to test IAST vulnerability sampling and ensure different hash values are generated.

### GET /iast/sampling-by-route-method-count-2/:key

Exactly the same content as the previous one, in different route and with different vulnerability hashes.

This endpoint must contain 15 different vulnerabilities, each on a separate line of code, regardless of their type, to test IAST vulnerability sampling and ensure different hash values are generated.

### POST /iast/sampling-by-route-method-count/:key

Exactly the same content as the previous one, but POST instead of GET and with different vulnerability hashes.

This endpoint must contain 15 different vulnerabilities, each on a separate line of code, regardless of their type, to test IAST vulnerability sampling and ensure different hash values are generated.

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

A GET request using a header `table` with any value. It will use its name, without it being hardcoded.

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

#### GET /iast/source/sql/test

An empty GET request that will execute two database queries, one to get a username and another to do a vulnerable SELECT using the obtained username.

### POST /iast/sc/*

These group of endpoints should trigger vulnerabilities detected by IAST with untrusted data coming from certain sources although the data is validated or sanitized by a configured security control

#### POST /iast/sc/s/configured

A post request using a parameter with a value that triggers a vulnerability. The value should be sanitized by a sanitizer security control configured for this vulnerability.

#### POST /sc/s/not-configured

A post request using a parameter  with a value that triggers a vulnerability. The value should be sanitized by a sanitizer security control that is not configured for this vulnerability.

#### POST /sc/s/all

A post request using a parameter with a value that triggers a vulnerability. The value should be sanitized by a sanitizer security control configured for all vulnerabilities.

#### POST /sc/iv/configured

A post request using a parameter with a value that triggers a vulnerability. The value should be validated by an input validator security control configured for this vulnerability.

#### POST /sc/iv/not-configured

A post request using a parameter with a value that triggers a vulnerability. The value should be validated by an input validator security control that is not configured for this vulnerability.

#### POST /sc/iv/all

A post request using a parameter  with a value that triggers a vulnerability. The value should be validated by an input validator security control configured for all vulnerabilities.

#### POST /sc/iv/overloaded/secure

A post request using two parameters that triggers a vulnerability. The values should be validated by an input validator security control with an overloaded method configured for all vulnerabilities.

#### POST /sc/iv/overloaded/insecure

A post request using two parameters that triggers a vulnerability. The values should be validated by an input validator security control with an overloaded method configured for other method signature.

#### POST /sc/s/overloaded/secure

A post request using a parameter with a value that triggers a vulnerability. The value should be sanitized by a sanitizer security control with an overloaded method configured for all vulnerabilities.

#### POST /sc/s/overloaded/insecure

A post request using a parameter with a value that triggers a vulnerability. The value should be sanitized by a sanitizer security control with an overloaded method configured for other method signature.

### GET /make_distant_call

This endpoint accept a mandatory parameter `url`. It'll make a call to these url, and should return a JSON response :

```js
{
    "url": "url",  // url in parameter
    "status_code": 200, // status code of the response
    "request_headers": {}, // request headers as a dict
    "response_headers": {} // response headers as a dict
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
    - Possible Values: `kafka`, `rabbitmq`, `sqs`, `kinesis`, `sns`
  - `message`: Specific message to produce and consume
  - `topic`: Name of messaging topic (if using `integration=sns`)
  - `queue`: Name of messaging queue (if using `integration=kafka|rabbitmq|sqs|sns (for sns->sqs tests)`)
  - `stream`: Name of messaging stream (if using `integration=kinesis`)
  - `exchange`: Name of messaging exchange (if using `integration=rabbitmq`)
  - `routingKey`: Name of message routing key (if using `integration=rabbitmq`)
  - `timeout`: Timeout in seconds

### GET /kafka/produce

This endpoint triggers Kafka producer calls.

Expected query params:
  - `topic`: Name of the Kafka topic to which the message will be produced.

### GET /kafka/consume

This endpoint triggers Kafka consumer calls.

Expected query params:
  - `topic`: Name of the Kafka topic from which the message will be consumed.
  - `timeout`: Timeout in seconds for the consumer operation.

### GET /sqs/produce

This endpoint triggers SQS producer calls.

Expected query params:
  - `queue`: Name of the SQS queue to which the message will be produced.
  - `message`: Specific message to be produced to the SQS queue.

### GET /sqs/consume

This endpoint triggers SQS consumer calls.

Expected query params:
  - `queue`: Name of the SQS queue from which the message will be consumed.
  - `timeout`: Timeout in seconds for the consumer operation.
  - `message`: Specific message to be consumed from the SQS queue.

### GET /sns/produce

This endpoint triggers SNS producer calls.

Expected query params:
  - `queue`: Name of the SQS queue associated with the SNS topic for message production.
  - `topic`: Name of the SNS topic to which the message will be produced.
  - `message`: Specific message to be produced to the SNS topic.

### GET /sns/consume

This endpoint triggers SNS consumer calls.

Expected query params:
  - `queue`: Name of the SQS queue associated with the SNS topic for message consumption.
  - `timeout`: Timeout in seconds for the consumer operation.
  - `message`: Specific message to be consumed from the SNS topic.

### GET /kinesis/produce

This endpoint triggers Kinesis producer calls.

Expected query params:
  - `stream`: Name of the Kinesis stream to which the message will be produced.
  - `timeout`: Timeout in seconds for the producer operation.
  - `message`: Specific message to be produced to the Kinesis stream.

### GET /kinesis/consume

This endpoint triggers Kinesis consumer calls.

Expected query params:
  - `stream`: Name of the Kinesis stream from which the message will be consumed.
  - `timeout`: Timeout in seconds for the consumer operation.
  - `message`: Specific message to be consumed from the Kinesis stream.

### GET /rabbitmq/produce

This endpoint triggers RabbitMQ producer calls.

Expected query params:
  - `queue`: Name of the RabbitMQ queue to which the message will be produced.
  - `exchange`: Name of the RabbitMQ exchange to which the message will be produced.
  - `routing_key`: Name of the RabbitMQ routing key for message production.

### GET /rabbitmq/consume

This endpoint triggers RabbitMQ consumer calls.

Expected query params:
  - `queue`: Name of the RabbitMQ queue from which the message will be consumed.
  - `exchange`: Name of the RabbitMQ exchange from which the message will be consumed.
  - `routing_key`: Name of the RabbitMQ routing key for message consumption.
  - `timeout`: Timeout in seconds for the consumer operation.

### GET /dsm/manual/produce

This endpoint sets a DSM produce operation manual API checkpoint. A 200 response with "ok" is returned along with the
base64 encoded context: `dd-pathway-ctx-base64`, which is returned within the response headers. Otherwise, error
messages will be returned.

Expected query params:
  - `type`: Type of DSM checkpoint, typically the system name such as 'kafka'
  - `target`: Target queue name

### GET /dsm/manual/produce_with_thread

This endpoint sets a DSM produce operation manual API checkpoint, doing so within another thread to ensure DSM context
API works cross-thread.  A 200 response with "ok" is returned along with the base64 encoded context:
`dd-pathway-ctx-base64`, which is returned within the response headers. Otherwise, error messages will be returned.

Expected query params:
  - `type`: Type of DSM checkpoint, typically the system name such as 'kafka'
  - `target`: Target queue name

### GET /dsm/manual/consume

This endpoint sets a DSM consume operation manual API checkpoint. The DSM base64 encoded context: `dd-pathway-ctx-base64`
should be included in the request headers under the `_datadog` header tag as a JSON formatted string. A 200 response with
text "ok" is returned upon success. Otherwise, error messages will be returned.

Expected query params:
  - `type`: Type of DSM checkpoint, typically the system name such as 'kafka'
  - `target`: Target queue name

### GET /dsm/manual/consume_with_thread

This endpoint sets a DSM consume operation manual API checkpoint, doing so within another thread to ensure DSM context
API works cross-thread. The DSM base64 encoded context `dd-pathway-ctx-base64` should be included in the request headers
under the `_datadog` header tag as a JSON formatted string. A 200 response with text "ok" is returned upon success.
Otherwise, error messages will be returned.

Expected query params:
  - `type`: Type of DSM checkpoint, typically the system name such as 'kafka'
  - `target`: Target queue name

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

### POST /user_login_success_event_v2

This endpoint calls the v2 of appsec event tracking SDK function used for user login success with
the data coming in the request body.

The parameters in the body are:
- `login`: String with the login data
- `user_id`: String with user identifier
- `metadata`: Objet with the metadata

### POST /user_login_failure_event_v2

This endpoint calls the v2 of appsec event tracking SDK function used for user login failure with
the data coming in the request body.

The parameters in the body are:
- `login`: String with the login data
- `exists`: String with "true" or "false" value
- `metadata`: Objet with the metadata

### GET '/inferred-proxy/span-creation'

This endpoint is supposed to be hit with the necessary headers that are used to create inferred proxy
spans for routers such as AWS API Gateway. Not including the headers means a span will not be created by the tracer
if the feature exists.

The endpoint supports the following query parameters:
 - `status_code`: str containing status code to used in API response

The headers necessary to create a span with example values:
  `x-dd-proxy-request-time-ms`: start time in milliseconds
  `x-dd-proxy-path`: "/api/data",
  `x-dd-proxy-httpmethod`: "GET",
  `x-dd-proxy-domain-name`: "system-tests-api-gateway.com",
  `x-dd-proxy-stage`: "staging",
  `x-dd-proxy`: "aws-apigateway",

### GET /users

This endpoint calls the appsec blocking SDK functions used for blocking users. If the expected parameter matches one of
the possible values the WAF will return the proper action.

Expected query parameters:
- `user`: user id.
  - Possible values: `blockedUser`

### GET /load_dependency

This endpoint loads a module/package in applicable languages. It's mainly used for telemetry tests to verify that
the `dependencies-loaded` event is appropriately triggered.

### GET /log/library

This endpoint facilitates logging a message using a logging library. It is primarily designed for testing log injection functionality. Weblog apps must log using JSON format.

The following query parameters are optional:
- `msg`: Specifies the message to be logged. If not provided, the default message "msg" will be logged.
- `level`: Specifies the log level to be used. If not provided, the default log level is "info".

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
Additionally, both methods support the following query parameters to use the sdk functions along with the authentication framework:
- `sdk_trigger`: when to call the sdk function, `after` or `before` the automated login event (by default `after`)
- `sdk_event`: login event type: `success` or `failure`.
- `sdk_user`: user id to be used in the sdk call.
- `sdk_mail`: user's mail to be used in the sdk call.
- `sdk_user_exists`: `true` of `false` to indicate whether the current user exists and populate the corresponding tag.

### \[POST\] /signup
This endpoint is used to create a new user. Do not keep the user in memory for later use, only call the framework method to pretend to do so.
Body fields accepted in POST method:
- `username`: the login name for the user.
- `password`: password for the user.

Additionally, the method supports the following query parameters to use the sdk functions along with the authentication framework:
- `sdk_event`: login event type: `signup`.
- `sdk_user`: user id to be used in the sdk call.
- `sdk_mail`: user's mail to be used in the sdk call.

### GET /debugger/*
These endpoints are used for the `Dynamic Instrumentation` tests.

#### GET /exceptionreplay/*
These endpoints will be used for `Exception Replay` tests.

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

### \[GET\] /rasp/multiple
The idea of this endpoint is to have an endpoint where multiple rasp operation take place. All of them will generate a MATCH on the WAF but none of them will block. The goal of this endpoint is to verify that the `rasp.rule.match` telemetry entry is updated properly. While this seems easy, the WAF requires that data given on `call` is passed as ephemeral and not as persistent.

In order to make the test easier, the operation used here need to generate LFI matches. The request will have two get parameters(`file1`, `file2`) which will contain a path that needs to be used as the parameters of the chosen lfi function. Then there will be another call to the lfi function with a harcoded parameter `'../etc/passwd'`. This will make `rasp.rule.match` to be equal to 3. A code example look like:

```
lfi_operation($request->get('file1'))
lfi_operation($request->get('file2'))
lfi_operation('../etc/passwd') //This one is harcoded
```

### GET /dsm/inject
This endpoint is used to validate DSM context injection injects the correct encoding to a header carrier.

### GET /dsm/extract
This endpoint is used to validate DSM context extraction works correctly when provided a headers carrier with the context already present within the headers.

### \[GET,POST\] /requestdownstream
This endpoint is used to test ASM Standalone propagation, by calling `/returnheaders` and returning its value (the headers received) to inspect them, looking for
distributed tracing propagation headers.

### \[GET\] /vulnerablerequestdownstream

Similar to `/requestdownstream`. This is used to test standalone IAST downstream propagation. It should call `/returnheaders` and return the resulting json data structure from `/returnheaders` in its response.

### \[GET,POST\] /returnheaders
This endpoint returns the headers received in order to be able to assert about distributed tracing propagation headers

### \[GET\] /stats-unique
The endpoint must accept a query string parameter `code`, which should be an integer. This parameter will be the status code of the response message, default to 200 OK.
This endpoint is used for client-stats tests to provide a separate "resource" via the endpoint path `stats-unique` to disambiguate those tests from other
stats generating tests.

### GET /healthcheck

Returns a JSON dict, with those values :

```js
{
  "status": "ok",
  "library": {
    "name": "<library's name>", // one of cpp, cpp_nginx, cpp_httpd, dotnet, golang, java, nodejs, php, python, ruby
    "version": "1.2.3" // version of the library
  }
}
```

### \[GET,POST\] /rasp/shi

This endpoint is used to test for shell injection attacks, consequently it must call a shell command by using a function or method which results in an actual shell being launched (e.g. /bin/sh). The chosen operation must be injected with the `GET` or `POST` parameter.

Query parameters and body fields required in the `GET` and `POST` method:
- `list_dir`: containing the string to inject on the shell command.

The endpoint should support the following content types in the `POST` method:
- `application/x-www-form-urlencoded`
- `application/xml`
- `application/json`

The chosen operation must use the file as provided, without any alterations, e.g.:
```
system("ls $list_dir");
```

Examples:
- `GET`: `/rasp/shi?list_dir=$(cat /etc/passwd 1>&2 ; echo .)
- `POST`: `{"list_dir": "$(cat /etc/passwd 1>&2 ; echo .)"}`

### \[GET,POST\] /rasp/cmdi

This endpoint is used to test for command injection attacks by executing a command without launching a shell.
The chosen operation must be injected with the `GET` or `POST` parameter.

Query parameters and body fields required in the `GET` and `POST` method:
- `command`: containing string or an array of strings to be executed as a command.

The endpoint should support the following content types in the `POST` method:
- `application/x-www-form-urlencoded`
- `application/xml`
- `application/json`

The chosen operation must use the file as provided, without any alterations, e.g.:
```
system("$command");
```

Examples:
- `GET`: `/rasp/cmdi?command=/usr/bin/touch /tmp/passwd
- `POST`: `{"command": ["/usr/bin/touch", "/tmp/passwd"]}`

### \[GET\] /set_cookie

This endpoint get a `name` and a `value` form the query string, and adds a header `Set-Cookie` with `{name}={value}` as header value in the HTTP response

### \[GET\] /session/new

This endpoint is the initial endpoint used to test session fingerprints, consequently it must initialize a new session and the web client should be able to deal with the persistence mechanism (e.g. cookies).

Returns the identifier of the created session id. Example :

```text
c377db41-b664-4e30-af57-5df2e803bec7
```

Examples:
- `GET`: `/session/new`

### **UNUSED** \[GET\] /session/user

Once a session has been established, a new call to `/session/user` must be made in order to generate a session fingerprint with the session id provided by the web client (e.g. cookie) and the user id provided as a parameter.

Query parameters required in the `GET` method:
- `sdk_user`: user id used in the WAF login event triggered during the execution of the request.

Examples:
- `GET`: `/session/user?sdk_user=sdkUser`

### \[GET\] /mock_s3/put_object

This endpoint is used to test the s3 integration. It creates a bucket if
necessary based on the `bucket` query parameter and puts an object at the `key`
query parameter. The body of the object is just the bytes of the key, encoded
with utf-8. Returns a result object with an `object` JSON object field containing the
`e_tag` field with the ETag of the uploaded object. The `e_tag` field has any
extra double-quotes stripped (accounting for a quirk in the boto3 library).

Examples:
- `GET`: `/mock_s3/put_object?bucket=somebucket&key=somekey`


### \[GET\] /mock_s3/copy_object

This endpoint is used to test the s3 integration. It creates a bucket if
necessary based on the `original_bucket` query parameter and puts an object at
the `original_key` query parameter. The body of the object is just the bytes of
the key, encoded with utf-8. The method then creates another `bucket` if
necessary and copies the object into the `key` location. Returns a result
object with an `object` JSON object field containing the `e_tag` field with the
ETag of the copied object. The `e_tag` field has any extra double-quotes
stripped (accounting for a quirk in the boto3 library).

Examples:
- `GET`: `/mock_s3/copy_object?original_bucket=somebucket&original_key=somekey&bucket=someotherbucket&key=someotherkey`


### \[GET\] /mock_s3/multipart_upload

This endpoint is used to test the s3 integration. It creates a bucket if
necessary based on the `bucket` query parameter and puts an object at the `key`
query parameter. The body of the object is just the bytes of the key, encoded
with utf-8, duplicated enough times to make two multipart uploads. Returns a
result object with an `object` JSON object field containing the `e_tag` field
with the ETag of the uploaded object returned by the final
CompleteMultipartUpload call. The `e_tag` field has any extra double-quotes
stripped (accounting for a quirk in the boto3 library).

Examples:
- `GET`: `/mock_s3/multipart_upload?bucket=somebucket&key=somekey`


### \[GET\] /mock_s3/copy_object

This endpoint is used to test the s3 integration. It creates a bucket if
necessary based on the `original_bucket` query parameter and puts an object at
the `original_key` query parameter. The body of the object is just the bytes of
the key, encoded with utf-8. The method then creates another `bucket` if
necessary and copies the object into the `key` location. Returns a result
object with an `object` JSON object field containing the `e_tag` field with the
ETag of the copied object. The `e_tag` field has any extra double-quotes
stripped (accounting for a quirk in the boto3 library).

Examples:
- `GET`: `/mock_s3/copy_object?original_bucket=somebucket&original_key=somekey&bucket=someotherbucket&key=someotherkey`


### \[GET\] /protobuf/serialize

This endpoint serializes a constant protobuf message. Returns the serialized message as a base64 encoded string. It is meant to be used to test the protobuf serialization integration.

Examples:
- `GET`: `/protobuf/serialize`

### \[GET\] /protobuf/deserialize

This endpoint deserializes a protobuf message from a base64 encoded string provided in the query parameters. Returns "ok" if deserialization is successful. The simplest way to use it is to pass the output of the `/protobuf/serialize` endpoint to it. It is meant to be used to test the protobuf deserialization integration.

Expected query params:
- `msg`: Base64 encoded protobuf message to deserialize

Examples:
- `GET`: `/protobuf/deserialize?msg=<base64_encoded_message>`
