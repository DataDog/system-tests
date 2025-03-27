package com.datadoghq.akka_http

import akka.http.scaladsl.model._
import akka.http.scaladsl.server.Directives._
import akka.http.scaladsl.server.Route
import scala.io.Source
import spray.json._
import scala.util.{Failure, Success, Try}

object HealthcheckRoutes {

  def route: Route = path("healthcheck") {
    get {
      val version: String = getVersion match {
        case Success(v) => v
        case Failure(_) => throw new RuntimeException("Can't get version")
      }

      val library = JsObject(
        "name" -> JsString("java"),
        "version" -> JsString(version)
      )

      val response = JsObject(
        "status" -> JsString("ok"),
        "library" -> library
      )

      complete(HttpEntity(ContentTypes.`application/json`, response.prettyPrint))
    }
  }

  private def getVersion: Try[String] = {
    Try {
      val source = Source.fromResource("dd-java-agent.version")
      val version = source.getLines().toList.headOption.getOrElse(throw new RuntimeException("File is empty"))
      source.close()
      version
    }
  }
}
