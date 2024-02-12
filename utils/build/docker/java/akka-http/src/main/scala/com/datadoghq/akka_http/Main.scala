package com.datadoghq.akka_http

import akka.http.scaladsl.Http
import akka.http.scaladsl.server.Directives._
import org.slf4j.LoggerFactory

import scala.concurrent.Future

object Main extends App {
  private val bindingFuture: Future[Http.ServerBinding] =
    Http().newServerAt("0.0.0.0", 7777).bindFlow(AppSecRoutes.route ~ IastRoutes.route)

  LoggerFactory.getLogger(this.getClass).info("Server online at port 7777")
}
