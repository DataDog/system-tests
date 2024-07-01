package com.datadoghq.akka_http

import akka.http.javadsl.marshallers.jackson.Jackson
import akka.http.scaladsl.model.{HttpEntity, MediaTypes}
import akka.http.scaladsl.server.Directives._
import akka.http.scaladsl.server.Route
import akka.http.scaladsl.unmarshalling.{FromEntityUnmarshaller, Unmarshaller}
import com.datadoghq.akka_http.Resources.dataSource
import com.fasterxml.jackson.annotation.JsonProperty

import scala.util.{Try, Using}
import scala.xml.{Elem, XML}

object RaspRoutes {

  private final val mapJsonUnmarshaller: Unmarshaller[HttpEntity, UserDTO] = {
    Jackson.unmarshaller(classOf[UserDTO])
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
            entity(Unmarshaller.messageUnmarshallerFromEntityUnmarshaller(mapJsonUnmarshaller)) { user =>
              complete(executeSql(user.userId))
            } ~ entity(as[UserDTO]) { user =>
            complete(executeSql(user.userId))
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


  private def executeSql(userId: String): Try[String] = {
    Using(dataSource.getConnection()) { conn =>
      val stmt = conn.prepareCall("select * from user where username = '" + userId + "'")
      val set = stmt.executeQuery();
      if (set.next()) {
        "ID: " + set.getLong("ID")
      } else {
        "User not found"
      }
    }
  }
}



