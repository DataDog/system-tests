package com.datadoghq.akka_http

import akka.http.scaladsl.model.{ContentTypes, HttpEntity, HttpResponse, StatusCodes}
import akka.http.scaladsl.server.Directives._
import akka.http.scaladsl.server.Route

object MainRoutes {

  val route: Route = path("sample_rate_route" / """\d{1,3}""".r) { (i) =>
    get {
      complete(
        HttpResponse(
          status = StatusCodes.OK,
          entity = HttpEntity(ContentTypes.`text/plain(UTF-8)`, "OK\n")
        )
      )
    }
  }

}
