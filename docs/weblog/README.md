# Weblog

A weblog is a web app that system uses to test the library. It mimics what would be a real instrumented HTTP application. A weblog app is required for each platform that the system tests will test. The weblog must implement a number of different endpoints.

## Disclaimer

This document describes endpoints implemented on weblog. Though, it's not a complete description, and can contains mistakes. The source of truth are the test itself. If a weblog endpoint passes system tests, then you can consider it as ok. And if it does not passes it, then you must correct it, even if it's in line with this document.

**You are strongly encouraged to help others by submitting corrections when you notice issues with this document.**

# Endpoints

All those endpoints must respond `200`. If content is not precised, it means that it's not tested. But for coherence, the content most used is precised.

## `GET /` and `POST /` (aka plain text endpoint)

The following text may be written to the body of the response:

```
Hello world!\n
```

## `GET /headers`

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

# GET /identify

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

# GET /identify-propagate

This endpoint must set the following tags on the local root span:

```
_dd.p.usr_id
```

The value of `_dd.p.usr.id` should be `dXNyLmlk`, which is the base64 encoding of `usr.id`.

## GET /params/%s

This endpoint must accept a parameter that is a string and is part of the URL path.

The following text may be written to the body of the response:

```
Hello world!\n
```

## GET /sample_rate_route/%i

This endpoint must accpect a parameter `i` as an integer.

The following text may be written to the body of the response:

```
Hello world!\n
```

## GET /spans

The endpoint may accept two query string parameters:

* `repeats` - this is the number of spans that should be manually created (default `1`). Span must be flatten (not nested)
* `garbage` - this is the number of tags that should added to each a span (default `1`). Tag must be of the form `garbage{i}: Random string`, `i` starting at `0`

The following text should be written to the body of the response:

```
Generated {repeats} spans with {garbage} garbage tags\n
```

Where `repeats` and `garbage` are the parameters read from the query string.

## GET /sqli

The endpoint must accept a query string parameter `q`. This parameter should be used as part of a query that is executed against a real database (to ensure a database span is created).

The output of the query should be written to the body of the response.

## `GET /status`

The endpoint must accept a query string parameter `code`, which should be an integer. This parameter will be the status code of the response message.

## \[All HTTP verbs\] /waf

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
## `GET /iast/insecure_hashing/deduplicate`

Parameterless endpoint. This endpoint contains a vulnerable souce code line (weak hashing) in a loop.

## `GET /iast/insecure_hashing/multiple_hash`

Parameterless endpoint. This endpoint contains 2 different insecure hashing operations (for example md5 and sha1). These operations are located in differents points of the executed source code.

## `GET /iast/insecure_hashing/test_secure_algorithm`

The endpoint executes a unique operation of String hashing with secure SHA-256 algorithm

The endpoint executes a unique operation of String hashing with given algorithm name

## GET /make_distant_call

This endpoint accept a mandatory parameter `url`. It'll make a call to these url, and should returns a JSON response :

```json
{
    "url": <url in paramter>,
    "status_code": <status code of the response>,
    "request_headers": <request headers as a dict>,
    "response_headers": <response headers as a dict>,
}
```

## `GET /iast/insecure_hashing/test_md5_algorithm`

The endpoint executes a unique operation of String hashing with unsecure MD5 algorithm

## GET /dbm

This endpoint executes database queries for DBM supported libraries. A 200 response is returned if the query
is executed successfully.

Expected query params:
  - `integration`: Name of DBM supported library
    - Possible Values: `psycopg`
  - `operation`: Method used to execute database statements
    - Possible Values: `execute`, `executemany`


Supported Libraries:
  - pyscopg (Python PostgreSQL adapter)
  - mysql (ADO.NET driver for MySQL)
  - npgsql (ADO.NET Data Provider for PostgreSQL)

## GET /dsm

This endpoint executes database queries for DSM supported libraries. A 200 response with message "ok" is returned
if the produce and consume calls for the specified tech are started successfully. Otherwise, error messages will
be returned.

Expected query params:
  - `integration`: Name of messaging tech
    - Possible Values: `kafka`, `rabbitmq`

## GET /user_login_success_event

This endpoint calls the appsec event tracking SDK function used for user login success.

By default, the generated event has the following specification:
- User ID: `system_tests_user`
- Metadata: `{metadata0: value0, metadata1: value1}`

Values can be changed with the query params called `event_user_id`.

## GET /user_login_failure_event

This endpoint calls the appsec event tracking SDK function used for user login failure.

By default, the generated event has the following specification:
- User ID: `system_tests_user`
- Exists: `true`
- Metadata: `{metadata0: value0, metadata1: value1}`

Values can be changed with the query params called `event_user_id` and `event_user_exists`.

## GET /custom_event

This endpoint calls the appsec event tracking SDK function used for custom events.

By default, the generated event has the following specification:
- Event name: `system_tests_event`
- Metadata: `{metadata0: value0, metadata1: value1}`

Values can be changed with the query params called `event_name`.

## GET /users

This endpoint calls the appsec blocking SDK functions used for blocking users. If the expected parameter matches one of
the possible values the WAF will return the proper action.

Expected query parameters:
- `user`: user id.
  - Possible values: `blockedUser`

## GET /load_dependency

This endpoint loads a module/package in applicable languages. It's mainly used for telemetry tests to verify that 
the `dependencies-loaded` event is appropriately triggered.

## GET /e2e_single_span

This endpoint will create two spans, a parent span (which is a root-span), and a child span.
The spans created are not sub-spans of the main root span automatically created by system-tests, but 
they will have the same `user-agent` containing the request ID in order to allow assertions on them.

The following query parameters are required:
- `parentName`: The name of the parent span (root-span).
- `childName`: The name of the child span (the parent of this span is the root-span identified by `parentName`).

The following query parameters are optional:
- `shouldIndex`: Valid values are `1` and `0`. When `shouldIndex=1` is provided, special tags are added in the spans that will force their indexation in the APM backend, without explicit retention filters needed.

This endpoint is used for the Single Spans tests (`test_single_span.py`).
