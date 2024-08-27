package controllers

import play.api.mvc._
import resources.Resources

import javax.inject.{Inject, Singleton}
import scala.util.Using

@Singleton
class RaspController @Inject()(cc: MessagesControllerComponents, res: Resources) extends AbstractController(cc) {

  def sqli = Action { request =>
    val userId = request.body match {
      case AnyContentAsFormUrlEncoded(data) =>
        data("user_id").head
      case AnyContentAsJson(data) =>
        (data \ "user_id").as[String]
      case AnyContentAsXml(data) =>
        data.text
      case _ =>
        request.queryString("user_id").head
    }
    Results.Ok(executeSql(userId))
  }

  private def executeSql(userId: String): String = {
    Using(res.dataSource.getConnection()) { conn =>
      val stmt = conn.createStatement()
      val set = stmt.executeQuery("SELECT * FROM users WHERE id='" + userId + "'")
      if (set.next()) {
        "ID: " + set.getLong("ID")
      } else {
        "User not found"
      }
    }.get
  }

}
