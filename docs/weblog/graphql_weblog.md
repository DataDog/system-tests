# GraphQL Weblog

GraphQL implementations are not necessarily tied to a particular transport. In order to be able to report on feature
parity for the various implementations that exist, they are tested using GraphQL specific Weblogs that have a dedicated
API.

GraphQL is not intrinsically bound to a particular transport, but the Weblogs for GraphQL expose the implementations via
a standardized HTTP API, so that all the tooling from common HTTP Weblogs can also easily be used to write GraphQL
system tests.

## Disclaimer

This document describes endpoints implemented on GraphQL weblogs. It may however not be a complete description and might
be inaccurate or otherwise out of date. The existing weblog implementations & tests using them are the ultimate source
of truth. If you notice this documentation is incorrect, and system tests for the actual implementation actually pass,
**you are strongly encouraged to submit corrections to this document if possible**.

## Endpoints

If there is a doubt on which HTTP server implementation to use, it is recommended to use the most standard one (part of
the standard library, or most widely used). Remember the point of GraphQL system tests is to verify GraphQL
functionality, not HTTP.

GraphQL weblogs are expected to expose two standardized endpoints on port `7777`:

### `GET /`

The endpoint at `/` serves as a heartbeat to determine when the Weblog is up and ready to serve requests.
Implementations must respond with `HTTP 200` when the service is ready. The body of the response is irrelevant and may
be empty.

### `POST /graphql`

> Many HTTP front-ends to GraphQL allow using the `GET` method to execute GraphQL queries while providing the details
> via query string parameters. It's okay for weblog implementations to support this, but system tests should not use
> this and consistently relies on the `POST` semantics instead.

#### Request

The `/graphql` endpoint exposes standard GraphQL operations over HTTP. It must accept requests where:

- The `Content-Type` header is set to `application/json`
- The request body is a JSON-encoded object with the following keys:
  - `query` - the GraphQL query to be executed
  - `variables` - variables provided by the client, to be used when resolving the GraphQL query
  - `operationName` - the name of the operation to execute within the query

#### GraphQL Schema & Semantics

The GraphQL middleware operates based on the following schema:

```graphql
# Required, but the implementation is a simple pass-through currently.
directive @case(format: String) on FIELD

type Query {
	user(id: Int!): User
	userByName(name: String): [User!]!
}

type User {
	id: Int!
	name: String!
}
```

A standard, hard-coded `User` database is defined as follows:
ID | Name
--:|-----
1  | `foo`
2  | `bar`
3  | `bar`

Querying `user` should return the `User` with the provided `id` if one exists, and `null` otherwise.

Querying `userByName` returns the list of `User`s for which the `Name` property matches the provided `name`. The
returned list may be empty.

#### Response

The Weblog must normally respond to all queries with an `HTTP 200` status code. The response body is a JSON-encoded
object with the following structure:
- `data` - the response of the GraphQL query
- `errors` - a list of errors produced while resolving the GraphQL Query (it may be omitted if empty)

> It is possible that the features being tested by certain system tests (such as those asserting request blocking
> functionality) may cause the server to respond with a non success status code.

### Anything else

Any other request should result in an `HTTP 404` response, although system tests must not rely on this behavior, as more
endpoints may be added in the future.
