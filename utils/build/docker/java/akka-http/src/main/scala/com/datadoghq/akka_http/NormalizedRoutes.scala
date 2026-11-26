package com.datadoghq.akka_http

import akka.http.scaladsl.server.Directives._
import akka.http.scaladsl.server.Route

// Routes for the RFC-1125 normalized route tests (tests/appsec/api_security_testing/test_normalized_route.py).
// akka-http path matchers do not name the values they extract, so only the routes whose normalized
// route has no parameter name are declared.
object NormalizedRoutes {

  val route: Route = get {
    concat(
      path("api_security" / "drafts") { complete("ok") },
      path("api_security" / "drafts" / "preview") { complete("ok") },
      path("api_security" / "encoded" / "café") { complete("ok") },
      pathPrefix("api_security" / "catch-all") { complete("ok") }
    )
  }
}
