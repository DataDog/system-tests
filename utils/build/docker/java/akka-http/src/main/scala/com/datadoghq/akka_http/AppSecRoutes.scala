package com.datadoghq.akka_http

import akka.http.scaladsl.Http
import akka.http.scaladsl.marshalling.Marshaller
import akka.http.scaladsl.model.Uri.Path
import akka.http.scaladsl.model._
import akka.http.scaladsl.model.headers._
import akka.http.scaladsl.server.Directives._
import akka.http.scaladsl.server.Route
import akka.http.scaladsl.unmarshalling._

import java.util
import scala.concurrent.Future
import scala.xml.{Elem, XML}

object AppSecRoutes {
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
      path("headers") {
        get {
          val entity = HttpEntity(ContentTypes.`text/plain(UTF-8)`, "012345678901234567890123456789012345678901")
          respondWithHeaders(RawHeader("Content-Language", "en-US")) {
            complete(entity)
          }
        }
      } ~
      path("tag_value" / Segment / """\d{3}""".r) { (value, code) =>
        get {
          parameter("content-language".?) { clo =>
            setRootSpanTag("appsec.events.system_tests_appsec_event.value", value)

            val resp = complete(
              HttpResponse(
                status = StatusCodes.custom(code.toInt, "some reason"),
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
              setRootSpanTag("appsec.events.system_tests_appsec_event.value", value)
              complete(
                HttpResponse(
                  status = StatusCodes.custom(code.toInt, "some reason"),
                  entity = HttpEntity(ContentTypes.`text/plain(UTF-8)`, "Value tagged")
                )
              )
            }
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
