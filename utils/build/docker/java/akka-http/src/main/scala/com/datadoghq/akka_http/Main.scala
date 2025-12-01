package com.datadoghq.akka_http

import akka.http.scaladsl.Http
import akka.http.scaladsl.model._
import akka.http.scaladsl.server.Directives._
import akka.http.scaladsl.server.Route

import com.datadoghq.system_tests.iast.infra.{LdapServer, SqlServer}
import org.slf4j.LoggerFactory

import scala.concurrent.Future
import scala.io.Source
import scala.util.{Failure, Success, Try}

object Main extends App {

  private val bindingFuture: Future[Http.ServerBinding] =
    Http().newServerAt("0.0.0.0", 7777).bindFlow(MainRoutes.route ~ AppSecRoutes.route ~ IastRoutes.route ~ RaspRoutes.route ~ HealthcheckRoutes.route)

  LoggerFactory.getLogger(this.getClass).info("Server online at port 7777")
}

object Resources {
  final val dataSource = new SqlServer().start
  final val ldapContext = new LdapServer().start
}
