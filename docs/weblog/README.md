# Weblog

A weblog is a web app that system uses to test the library. A weblog app is required for each platform that the system tests will test. The weblog must implement a number of different end points.

# Endpoints

## GET / (aka plain text end point)

The following text should be written to the body of the response:

```
Hello world!\n
```

## GET /headers

This end point should set the following headers:

```
content-type: text
content-length: 16
content-language: en-US
```

The following text should be written to the body of the response:

```
Hello headers!\n
```

# GET /identify

This endpoint should set the following tags on the local root span:

```
usr.id
usr.email
usr.name
usr.session_id
usr.role
usr.scope
```

The value of each tag should be the tag name, for example `usr.id` should be set to `usr.id`.

## GET /params/%s

This end point should accept a parameter that is a string and is part of the URL path.

The following text should be written to the body of the response:

```
Hello world!\n
```

## GET /sample_rate_route/%i

The following text should be written to the body of the response:

```
Hello world!\n
```

## GET /spans

The end point should accept two query string parameters:

* `repeats` - this is the number of spans that should be manually created
* `garbage` - this is the number of tags that should added to each a span

The following text should be written to the body of the response:

```
Generated {repeats} spans with {garbage} garbage tags\n
```

Where `repeats` and `garbage` are the parameters read from the query string.

## GET /sqli

The end point should accept a query string parameter `q`. This parameter should be used as part of a query that is executed against a real database (to ensure a database span is created).

The output of the query should be written to the body of the response.

## GET /waf

The following text should be written to the body of the response:

```
Hello world!\n
```
