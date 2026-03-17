package com.datadoghq.akka_http

import akka.http.scaladsl.model.{ContentTypes, HttpEntity, HttpResponse, StatusCode, StatusCodes}
import akka.http.scaladsl.server.Directives._
import akka.http.scaladsl.server.Route

object MainRoutes {

  val route: Route =
    path("sample_rate_route" / """\d{1,3}""".r) { (i) =>
      get {
        complete(
          HttpResponse(
            status = StatusCodes.OK,
            entity = HttpEntity(ContentTypes.`text/plain(UTF-8)`, "OK\n")
          )
        )
      }
    } ~
    pathPrefix("resource_renaming") {
      get {
        complete(
          HttpResponse(
            status = StatusCodes.OK,
            entity = HttpEntity(ContentTypes.`text/plain(UTF-8)`, "ok")
          )
        )
      }
    } ~
    pathPrefix("inferred-proxy") {
      path("span-creation") {
        get {
          parameters("status_code".?) { statusCodeParam =>
            extractRequest { req =>
              println("Received an API Gateway request:")
              req.headers.foreach(h => println(s"${h.name}: ${h.value}"))
              val code = statusCodeParam match {
                case Some(s) => try { s.toInt } catch { case _: NumberFormatException => 400 }
                case None => 200
              }
              val status: StatusCode = StatusCodes.getForKey(code).getOrElse(StatusCodes.custom(code, "Custom", "Custom"))
              complete(HttpResponse(status = status, entity = HttpEntity(ContentTypes.`text/plain(UTF-8)`, "ok")))
            }
          }
        }
      }
    }

}
