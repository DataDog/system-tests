package controllers

import akka.stream.Materializer
import akka.stream.javadsl.Sink
import akka.util.ByteString
import datadog.appsec.api.blocking.Blocking
import datadog.trace.api.interceptor.MutableSpan
import io.opentracing.util.GlobalTracer
import play.api.libs.json.{Json, Writes}
import play.api.libs.ws.ahc.{AhcWSClient, AhcWSRequest, StandaloneAhcWSResponse}
import play.api.libs.ws.{WSClient, WSRequest}
import play.api.mvc._
import play.shaded.ahc.org.asynchttpclient.{AsyncCompletionHandler, AsyncHttpClient, Request => AHCRequest, Response => AHCResponse}

import java.util
import javax.inject.{Inject, Singleton}
import scala.concurrent.{ExecutionContext, Future, Promise}

@Singleton
class AppSecController @Inject()(cc: MessagesControllerComponents, ws: WSClient, mat: Materializer)
                                (implicit ec: ExecutionContext) extends AbstractController(cc) {
  def index = Action {
    val span = tracer.buildSpan("test-span").start
    span.setTag("test-tag", "my value")
    withSpan(span) {
      Results.Ok("Hello world!")
    }
  }

  def headers = Action {
    Results.Ok("012345678901234567890123456789012345678901")
      .as("text/plain; charset=utf-8")
      .withHeaders("Content-Language" -> "en-US")
  }


  def tagValue(value: String, code: Int) = Action { request =>
    setRootSpanTag("appsec.events.system_tests_appsec_event.value", value)

    val result = Results.Status(code)("Value tagged")
      .as("text/plain; charset=utf-8")

    request.queryString.get("content-language").flatMap(_.headOption) match {
      case Some(cl) => result.withHeaders(CONTENT_LANGUAGE -> cl)
      case None => result
    }
  }

  def tagValuePost(value: String, code: Int) = Action { request =>
    request.body.asFormUrlEncoded // needs to be read, though we do nothing with it

    setRootSpanTag("appsec.events.system_tests_appsec_event.value", value)

    Results.Status(code)("Value tagged")
      .as("text/plain; charset=utf-8")
  }

  def params(segments: Seq[String]) = Action {
    Results.Ok(segments.toString())
  }

  def waf = Action {
    Results.Ok("Hello world!")
  }

  def wafPost = Action { request =>
    request.body match {
      case AnyContentAsFormUrlEncoded(data) =>
        Results.Ok(data.toString())
      case AnyContentAsMultipartFormData(mpfd) =>
        Results.Ok(mpfd.dataParts.toString())
      case AnyContentAsJson(data) =>
        Results.Ok(Json.stringify(data))
      case AnyContentAsXml(data) =>
        Results.Ok(data.toString())
      case AnyContentAsRaw(data) =>
        Results.Ok(s"Hello world (${data.size})")
      case AnyContentAsText(data) =>
        Results.Ok(data)
      case anything =>
        Results.Ok(anything.toString)
    }
  }

  def distantCall(url: String) = Action.async {
    val remoteReq: WSRequest = ws.url(url).withMethod("GET")

    // we need to break the abstraction to be able to get to the request headers
    val ahcRequest: AHCRequest = remoteReq.asInstanceOf[AhcWSRequest].underlying.buildRequest()

    executeAHCRequest(ahcRequest).map { resp: StandaloneAhcWSResponse =>
      resp.bodyAsSource.runWith(Sink.ignore[ByteString]())(mat)
      val dcr = DistantCallResponse.create(url, resp.status, ahcRequest.getHeaders, resp.headers)
      Results.Ok(Json.toJson(dcr))
    }
  }

  private def executeAHCRequest(request: AHCRequest): Future[StandaloneAhcWSResponse] = {
    val result = Promise[StandaloneAhcWSResponse]()
    val handler = new AsyncCompletionHandler[AHCResponse]() {
      override def onCompleted(response: AHCResponse): AHCResponse = {
        result.success(StandaloneAhcWSResponse(response))
        response
      }

      override def onThrowable(t: Throwable): Unit = {
        result.failure(t)
      }
    }

    ws.asInstanceOf[AhcWSClient].underlying[AsyncHttpClient].executeRequest(request, handler)
    result.future
  }

  def status(code: Int) = Action {
    Results.Status(code)
  }

  def users(user: String) = Action {
    var span = GlobalTracer.get().activeSpan()
    span match {
      case span1: MutableSpan =>
        var localRootSpan = span1.getLocalRootSpan()
        localRootSpan.setTag("usr.id", user);
      case _ =>
    }
    Blocking
      .forUser(user)
      .blockIfMatch();
    Results.Ok(s"Hello $user")
  }

  def loginSuccess(event_user_id: Option[String]) = Action {
    eventTracker.trackLoginSuccessEvent(event_user_id.getOrElse("system_tests_user"), metadata)
    Results.Ok("ok")
  }

  def loginFailure(event_user_id: Option[String], event_user_exists: Option[Boolean]) = Action {
    eventTracker.trackLoginFailureEvent(
      event_user_id.getOrElse("system_tests_user"), event_user_exists.getOrElse(true), metadata)
    Results.Ok("ok")
  }

  def customEvent(event_name: Option[String]) = Action {
    eventTracker.trackCustomEvent(event_name.getOrElse("system_tests_event"), metadata)
    Results.Ok("ok")
  }

  case class DistantCallResponse(
                                  url: String,
                                  status_code: Int,
                                  request_headers: Map[String, String],
                                  response_headers: Map[String, String]
                                )

  object DistantCallResponse {
    def create(url: String, status_code: Int, request_headers: java.lang.Iterable[java.util.Map.Entry[String, String]],
               response_headers: Map[String, scala.collection.Seq[String]]): DistantCallResponse = {
      apply(url, status_code, convertIterable(request_headers), convertMap(response_headers.view.mapValues(_.toSeq).toMap))
    }

    private def convertMap(m: Map[String, Seq[String]]) : Map[String, String] =
      m.flatMap {
        case (key, Seq(value, _*)) => Some(key, value)
        case _ => None
      }

    private def convertIterable(it: java.lang.Iterable[java.util.Map.Entry[String, String]]) : Map[String, String] = {
      import scala.jdk.CollectionConverters._
      it.asScala.map(entry => entry.getKey -> entry.getValue).toMap
    }

  }

  implicit val distantCallRespWrites: Writes[DistantCallResponse] = Json.writes[DistantCallResponse]

  private val metadata: util.Map[String, String] = {
    val h = new util.HashMap[String, String]
    h.put("metadata0", "value0")
    h.put("metadata1", "value1")
    h
  }
}
