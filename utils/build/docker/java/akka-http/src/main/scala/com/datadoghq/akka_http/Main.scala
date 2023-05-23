package com.datadoghq.akka_http

import akka.http.javadsl.marshallers.jackson.Jackson
import akka.http.scaladsl.Http
import akka.http.scaladsl.model._
import akka.http.scaladsl.model.headers.{RawHeader, `Content-Length`}
import akka.http.scaladsl.server.Directives._
import akka.http.scaladsl.unmarshalling.Unmarshaller
import datadog.trace.api.{GlobalTracer => DDGlobalTracer}
import org.slf4j.LoggerFactory

import scala.concurrent.Future

object Main extends App {
  private def testSpan = {
    val span = tracer.buildSpan("test-span").start()
    span.setTag("test-tag", "my value")
    span
  }

  private val entityToJsonUnmarshaller : Unmarshaller[HttpEntity, Object] = Jackson.unmarshaller(classOf[Object]).asScala
  private val jsonUnmarshaller = Unmarshaller.strict[HttpRequest, HttpEntity](_.entity).andThen(entityToJsonUnmarshaller)

  private val route =
    path("") {
      get {
        val span = testSpan
        complete {
          try "Hello World!" finally span.finish()
        }
      }
    } ~
      path("headers") {
        get {
          respondWithHeader(RawHeader("Content-Language", "en-US")) {
            complete(
              "012345678901234567890123456789012345678901"
            )
          }
        }
      } ~
      path("params" / Segments) { pathSegments =>
        get {
          complete {
            pathSegments.toString()
          }
        }
      } ~
      path("waf") {
        post {
          entity(as[FormData]) { formData =>
            complete(formData.fields.toMultiMap.toString)
          } ~
          entity(as[Object](jsonUnmarshaller)) { json =>
            complete(json.toString)
          }
        }
      } ~
      path("status") {
        get {
          parameter("code".as[Int]) { code =>
            complete(StatusCode.int2StatusCode(code), code.toString)
          }
        }
      } ~
      path("user_login_success_event") {
        get {
          parameter("event_user_id".?("system_tests_user")) { uid =>
            DDGlobalTracer.getEventTracker.trackLoginSuccessEvent(uid, metadata)
            complete("ok")
          }
        }
      } ~
      path("user_login_failure_event") {
        get {
          parameters(
            "event_user_id".?("system_tests_user"),
            "event_user_exists".as[Boolean].?(true)
          ) { (uid, event_user_exists) =>
            DDGlobalTracer.getEventTracker.trackLoginFailureEvent(
              uid, event_user_exists, metadata)
            complete("ok")
          }
        }
      } ~
      path("custom_event") {
        get {
          parameter("event_name".?("system_tests_event")) { eventName =>
            DDGlobalTracer.getEventTracker.trackCustomEvent(eventName, metadata)
            complete("ok")
          }
        }
      }

  private val metadata : java.util.Map[String, String] = {
    val h = new java.util.HashMap[String, String]()
    h.put("metadata0", "value0")
    h.put("metadata1", "value1")
    h
  }

  private val bindingFuture: Future[Http.ServerBinding] =
    Http().newServerAt("0.0.0.0", 7777).bindFlow(route ~ IastRoutes.route)

  LoggerFactory.getLogger(this.getClass).info("Server online at port 7777")
}
