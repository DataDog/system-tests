package controllers

import akka.stream.Materializer
import play.api.libs.ws.WSClient
import play.api.mvc._

import javax.inject.{Inject, Singleton}
import scala.concurrent.ExecutionContext

@Singleton
class MainController @Inject()(cc: MessagesControllerComponents, ws: WSClient, mat: Materializer)
                              (implicit ec: ExecutionContext) extends AbstractController(cc) {

  def sampleRateRoute(i: Int) = Action { request =>
    Results.Status(200)("OK!\n")
      .as("text/plain; charset=utf-8")
  }
}
