package controllers

import com.datadoghq.system_tests.iast.utils._
import play.api.mvc._
import resources.Resources

import java.io.File
import java.net.{MalformedURLException, URL, URLConnection}

import javax.inject.{Inject, Singleton}
import scala.util.Using

@Singleton
class RaspController @Inject()(cc: MessagesControllerComponents, res: Resources) extends AbstractController(cc) {

  private val cmdExamples = new CmdExamples()

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

  def lfi = Action { request =>
    val file = request.body match {
      case AnyContentAsFormUrlEncoded(data) =>
        data("file").head
      case AnyContentAsJson(data) =>
        (data \ "file").as[String]
      case AnyContentAsXml(data) =>
        data.text
      case _ =>
        request.queryString("file").head
    }
    Results.Ok(executeLfi(file))
  }

  def ssrf = Action { request =>
    val domain = request.body match {
      case AnyContentAsFormUrlEncoded(data) =>
        data("domain").head
      case AnyContentAsJson(data) =>
        (data \ "domain").as[String]
      case AnyContentAsXml(data) =>
        data.text
      case _ =>
        request.queryString("domain").head
    }
    Results.Ok(executeUrl(domain))
  }

  def shi = Action { request =>
    val cmd = request.body match {
      case AnyContentAsFormUrlEncoded(data) =>
        data("list_dir").head
      case AnyContentAsJson(data) =>
        (data \ "list_dir").as[String]
      case AnyContentAsXml(data) =>
        data.text
      case _ =>
        request.queryString("list_dir").head
    }
    Results.Ok(executeShi(cmd))
  }

  def cmdi = Action { request =>
    val command = request.body match {
      case AnyContentAsFormUrlEncoded(data) =>
        data("command").toArray
      case AnyContentAsJson(data) =>
        (data \ "command").as[Array[String]]
      case AnyContentAsXml(data) =>
        (data \\ "cmd").map(_.text).toArray
      case _ =>
        request.queryString("command").toArray
    }
    Results.Ok(executeCmdi(command))
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

  private def executeLfi(file: String): String = {
    new File(file)
    "OK"
  }

  private def executeShi(cmd: String): String = {
    cmdExamples.insecureCmd(cmd)
    "OK"
  }

  private def executeCmdi(arrayCmd: Array[String]): String = {
    cmdExamples.insecureCmd(arrayCmd)
    "OK"
  }

  def executeUrl(urlString: String): String = {
    try {
      val url = try {
        new URL(urlString)
      } catch {
        case _: MalformedURLException =>
          new URL("http://" + urlString)
      }

      val connection: URLConnection = url.openConnection()
      connection.connect()
      "OK"
    } catch {
      case e: Exception =>
        e.printStackTrace()
        "http connection failed"
    }
  }

}
