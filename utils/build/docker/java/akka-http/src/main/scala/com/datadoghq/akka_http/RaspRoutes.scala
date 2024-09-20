package com.datadoghq.akka_http

import akka.http.javadsl.marshallers.jackson.Jackson
import akka.http.scaladsl.model.{HttpEntity, MediaTypes}
import akka.http.scaladsl.server.Directives._
import akka.http.scaladsl.server.Route
import akka.http.scaladsl.unmarshalling.{FromEntityUnmarshaller, Unmarshaller}
import com.datadoghq.akka_http.Resources.dataSource
import com.fasterxml.jackson.annotation.JsonProperty

import java.io.File

import scala.util.{Try, Using}
import scala.xml.{Elem, XML}

object RaspRoutes {

  private final val mapUserJsonUnmarshaller: Unmarshaller[HttpEntity, UserDTO] = {
    Jackson.unmarshaller(classOf[UserDTO])
      .asScala
      .forContentTypes(MediaTypes.`application/json`)
  }

  private final val mapFileJsonUnmarshaller: Unmarshaller[HttpEntity, FileDTO] = {
    Jackson.unmarshaller(classOf[FileDTO])
      .asScala
      .forContentTypes(MediaTypes.`application/json`)
  }

  val route: Route = pathPrefix("rasp") {
    pathPrefix("sqli") {
      get {
        parameter("user_id") { userId =>
          complete(executeSql(userId))
        }
      } ~
        post {
          formFieldMap { fields: Map[String, String] =>
            complete(executeSql(fields("user_id")))
          } ~
            entity(Unmarshaller.messageUnmarshallerFromEntityUnmarshaller(mapUserJsonUnmarshaller)) { user =>
              complete(executeSql(user.userId))
            } ~ entity(as[UserDTO]) { user =>
            complete(executeSql(user.userId))
          }
        }
    } ~
      pathPrefix("lfi") {
        get {
          parameter("file") { file =>
            complete(executeFli(file))
          }
        } ~
          post {
            formFieldMap { fields: Map[String, String] =>
              complete(executeFli(fields("file")))
            } ~
              entity(Unmarshaller.messageUnmarshallerFromEntityUnmarshaller(mapFileJsonUnmarshaller)) { file =>
                complete(executeFli(file.file))
              } ~ entity(as[FileDTO]) { file =>
              complete(executeFli(file.file))
            }
          }
      }

  }

  case class UserDTO(@JsonProperty("user_id") userId: String) {}

  implicit val userXmlUnmarshaller: FromEntityUnmarshaller[UserDTO] =
    Unmarshaller.stringUnmarshaller.forContentTypes(MediaTypes.`text/xml`, MediaTypes.`application/xml`).map { string =>
      val xmlData: Elem = XML.loadString(string)
      val userId = xmlData.text
      UserDTO(userId)
    }

  case class FileDTO(@JsonProperty("file") file: String) {}

  implicit val fileXmlUnmarshaller: FromEntityUnmarshaller[FileDTO] =
    Unmarshaller.stringUnmarshaller.forContentTypes(MediaTypes.`text/xml`, MediaTypes.`application/xml`).map { string =>
      val xmlData: Elem = XML.loadString(string)
      val file = xmlData.text
      FileDTO(file)
    }


  private def executeSql(userId: String): Try[String] = {
    Using(dataSource.getConnection()) { conn =>
      val stmt = conn.createStatement()
      val set = stmt.executeQuery("SELECT * FROM users WHERE id='" + userId + "'")
      if (set.next()) {
        "ID: " + set.getLong("ID")
      } else {
        "User not found"
      }
    }
  }

  private def executeFli(file: String): Try[String] = {
    new File(file)
    Try("ok")
  }
}



