package com.datadoghq.akka_http

import akka.http.scaladsl.Http
import akka.http.scaladsl.marshalling.Marshaller
import akka.http.scaladsl.model.Uri.Path
import akka.http.scaladsl.model._
import akka.http.scaladsl.model.headers._
import akka.http.scaladsl.server.Directives._
import akka.http.scaladsl.server.Route
import datadog.appsec.api.blocking.Blocking
import datadog.trace.api.interceptor.MutableSpan
import io.opentracing.util.GlobalTracer
import com.datadoghq.system_tests.iast.utils.Utils
import com.datadoghq.system_tests.iast.utils.CryptoExamples

import scala.concurrent.blocking
import akka.http.javadsl.marshallers.jackson.Jackson
import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.scala.DefaultScalaModule
import akka.http.scaladsl.model.{HttpEntity, MediaTypes}
import akka.http.scaladsl.unmarshalling.{FromEntityUnmarshaller, Unmarshaller}

import java.util
import scala.concurrent.Future
import scala.xml.{Elem, XML}

import datadog.appsec.api.user.User.setUser

import java.util.Collections.emptyMap
import scala.jdk.CollectionConverters._

object AppSecRoutes {

  private val cryptoExamples = new CryptoExamples()

  val objectMapper = new ObjectMapper().registerModule(DefaultScalaModule)
  implicit val jsonNodeUnmarshaller: FromEntityUnmarshaller[JsonNode] =
    Jackson.unmarshaller(objectMapper, classOf[JsonNode])
      .asScala
      .forContentTypes(MediaTypes.`application/json`)

  val route: Route =
    path("") {
      get {
        val span = tracer.buildSpan("test-span").start
        span.setTag("test-tag", "my value")
        withSpan(span) {
          complete("Hello world!")
        }
      }
    } ~
    path("createextraservice") {
      get {
        parameter("serviceName") { serviceName =>
          setRootSpanTag("service", serviceName)
          complete("OK")
        }
      }
    } ~
      path("headers") {
        get {
          val entity = HttpEntity(ContentTypes.`text/plain(UTF-8)`, "012345678901234567890123456789012345678901")
          respondWithHeaders(RawHeader("Content-Language", "en-US")) {
            complete(entity)
          }
        }
      } ~
      path("tag_value" / Segment / """\d{3}""".r) { (tag_value, status_code) =>
        get {
          parameter("content-language".?) { clo =>
            setRootSpanTag("appsec.events.system_tests_appsec_event.value", tag_value)

            val resp = complete(
              HttpResponse(
                status = StatusCodes.custom(status_code.toInt, "some reason"),
                entity = HttpEntity(ContentTypes.`text/plain(UTF-8)`, "Value tagged")
              )
            )

            clo match {
              case Some(cl) => respondWithHeaders(RawHeader("Content-Language", cl)) { resp }
              case None => resp
            }
          }
        } ~
          post {
            formFieldMap { _ =>
              setRootSpanTag("appsec.events.system_tests_appsec_event.value", tag_value)
              complete(
                HttpResponse(
                  status = StatusCodes.custom(status_code.toInt, "some reason"),
                  entity = HttpEntity(ContentTypes.`text/plain(UTF-8)`, "Value tagged")
                )
              )
            } ~ (entity(as[JsonNode])) { _ =>
              setRootSpanTag("appsec.events.system_tests_appsec_event.value", tag_value)
              complete(
                HttpResponse(
                  status = StatusCodes.custom(status_code.toInt, "some reason"),
                  entity = HttpEntity(ContentTypes.`text/plain(UTF-8)`, "Value tagged")
                )
              )
            }
          }
      } ~
      path("api_security/sampling" / """\d{3}""".r) { (i) =>
        get {
          complete(
            HttpResponse(
              status = StatusCodes.custom(i.toInt, "some reason"),
              entity = HttpEntity(ContentTypes.`text/plain(UTF-8)`, "Hello!\n")
            )
          )
        }
      } ~
      path("api_security_sampling" / """\d{2,3}""".r) { (i) =>
        get {
          complete(
            HttpResponse(
              status = StatusCodes.OK,
              entity = HttpEntity(ContentTypes.`text/plain(UTF-8)`, "OK!\n")
            )
          )
        }
      } ~
      path("params" / Segments) { segments: Seq[String] =>
        get {
          complete(segments.toString())
        }
      } ~
      path("waf") {
        get {
          complete("Hello world!")
        } ~
          post {
            formFieldMultiMap { fields: Map[String, List[String]] =>
              complete(fields.toString)
            } ~
              entity(Unmarshaller.messageUnmarshallerFromEntityUnmarshaller(generalizedJsonUnmarshaller)) { value =>
                complete(value.toString)
              } ~ entity(as[XmlObject]) { xmlObj =>
              complete(xmlObj.toString)
            } ~
              entity(Unmarshaller.messageUnmarshallerFromEntityUnmarshaller(
                Unmarshaller.byteArrayUnmarshaller.forContentTypes(
                  MediaTypes.`application/octet-stream`))) { arr: Array[Byte] =>
                complete(s"Hello world (${arr.length})")
              } ~
              entity(as[String]) { s: String =>
                // interpret as string as fallback, regardless of content-type
                complete(s)
              }
          }
      } ~
      path("waf" / RemainingPath) { remaining: Path =>
        get {
          complete(remaining.toString())
        }
      } ~
      path("make_distant_call") {
        get {
          parameter("url") { url =>
            complete(StatusCodes.OK, makeDistantCall(url))(Marshaller.futureMarshaller(jsonMarshaller))
          }
        }
      } ~
      path("status") {
        get {
          parameter("code".as[Int]) { code =>
            complete(StatusCodes.custom(code, "whatever reason"))
          }
        }
      } ~
      path("users") {
        get {
          parameter("user") { user =>
            var span = GlobalTracer.get().activeSpan()
            span match {
              case span1: MutableSpan =>
                var localRootSpan = span1.getLocalRootSpan()
                localRootSpan.setTag("usr.id", user)
              case _ =>
            }
            Blocking.forUser(user).blockIfMatch()
            complete(s"Hello ${user}")
          }
        }
      } ~
      path("identify") {
        get {
          setUser(
            "usr.id",
            Map.apply(
              "email" -> "usr.email",
              "name" -> "usr.name",
              "session_id" -> "usr.session_id",
              "role" -> "usr.role",
              "scope" -> "usr.scope"
            ).asJava
          )
          complete("OK")
        }
      } ~
      path("user_login_success_event") {
        get {
          parameter("event_user_id".?("system_tests_user")) { userId =>
            eventTracker.trackLoginSuccessEvent(userId, metadata)
            complete("ok")
          }
        }
      } ~
      path("user_login_failure_event") {
        get {
          parameters("event_user_id".?("system_tests_user"),
            "event_user_exists".as[Boolean].?(true)) { (userId, userExists) =>
            eventTracker.trackLoginFailureEvent(userId, userExists, metadata)
            complete("ok")
          }
        }
      } ~
      path("custom_event") {
        get {
          parameter("event_name".?("system_tests_event")) { eventName =>
            eventTracker.trackCustomEvent(eventName, metadata)
            complete("ok")
          }
        }
      } ~
      path("requestdownstream") {
        blocking {
            var url = "http://localhost:7777/returnheaders";
            var json = Utils.sendGetRequest(url);
            complete(json)
          }
      } ~
      path("vulnerablerequestdownstream") {
        blocking {
          cryptoExamples.insecureMd5Hashing("password")
          var url = "http://localhost:7777/returnheaders";
          var json = Utils.sendGetRequest(url);
          complete(json)
        }
      } ~
      path("returnheaders") {
        get {
          extractRequest { request =>
            val headers = request.headers.map(header => header.name() -> header.value()).toMap
            complete(StatusCodes.OK, headers)(jsonMarshaller)
          }
        }
      } ~
      path("set_cookie") {
        get {
          parameters('name.as[String], 'value.as[String]) { (name, value) =>
            val cookieHeader = RawHeader("Set-Cookie", HttpCookiePair(name, value).toString())
            respondWithHeader(cookieHeader) {
              complete("ok")
            }
          }
        }
      }


  case class XmlObject(value: String, attack: String)

  implicit val xmlObjectUnmarshaller: FromEntityUnmarshaller[XmlObject] =
    Unmarshaller.stringUnmarshaller.forContentTypes(MediaTypes.`text/xml`, MediaTypes.`application/xml`).map { string =>
      val xmlData: Elem = XML.loadString(string)
      val value = (xmlData \ "value").text
      val attack = (xmlData \ "attack").text
      XmlObject(value, attack)
    }

  case class DistantCallResponse(
                                  url: String,
                                  status_code: Int,
                                  request_headers: Map[String, String],
                                  response_headers: Map[String, String]
                                )

  private def makeDistantCall(url: String): Future[DistantCallResponse] = {
    val request = HttpRequest(uri = url)
    val requestHeaders = request.headers.map(h => (h.name(), h.value())).toMap

    Http().singleRequest(request).map { response =>
      val statusCode = response.status.intValue()
      val responseHeaders = response.headers.map(h => (h.name(), h.value())).toMap

      response.discardEntityBytes()

      DistantCallResponse(
        url = url,
        status_code = statusCode,
        request_headers = requestHeaders,
        response_headers = responseHeaders,
      )
    }
  }

  private val metadata: util.Map[String, String] =  {
    val h = new util.HashMap[String, String]
    h.put("metadata0", "value0")
    h.put("metadata1", "value1")
    h
  }
}
