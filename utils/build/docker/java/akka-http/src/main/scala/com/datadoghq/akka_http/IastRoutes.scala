package com.datadoghq.akka_http

import akka.http.javadsl.marshallers.jackson.Jackson
import akka.http.scaladsl.marshalling.Marshaller
import akka.http.scaladsl.model.{HttpEntity, RequestEntity, StatusCodes}
import akka.http.scaladsl.server.Directives._
import akka.http.scaladsl.server.Route
import akka.http.scaladsl.unmarshalling.Unmarshaller
import com.datadoghq.system_tests.iast.infra.{LdapServer, SqlServer}
import com.datadoghq.system_tests.iast.utils._

import java.sql.Statement

object IastRoutes {
  private val dataSource = new SqlServer().start
  private val ldapContext = new LdapServer().start

  private val superSecretAccessKey = "insecure"
  private val cmd = new CmdExamples()
  private val crypto = new CryptoExamples()
  private val ldap = new LDAPExamples(ldapContext)
  private val path_ = new PathExamples()
  private val sql = new SqlExamples(dataSource)

  val route: Route = pathPrefix("iast") {
    pathPrefix("insecure_hashing") {
      get {
        path("deduplicate") {
          complete(crypto.removeDuplicates(superSecretAccessKey))
        } ~
          path("multiple_hash") {
            complete(crypto.multipleInsecureHash(superSecretAccessKey))
          } ~
          path("test_secure_algorithm") {
            complete(crypto.secureHashing(superSecretAccessKey))
          } ~
          path("test_md5_algorithm") {
            complete(crypto.insecureMd5Hashing(superSecretAccessKey))
          }
      }
    } ~
      pathPrefix("insecure_cipher") {
        get {
          path("test_secure_algorithm") {
            complete(crypto.secureCipher(superSecretAccessKey))
          } ~
            path("test_insecure_algorithm") {
              complete(crypto.insecureCipher(superSecretAccessKey))
            }
        }
      } ~
      pathPrefix("sqli") {
        post {
          path("test_insecure") {
            paramOrFormFields("username", "password") { (username, password) =>
              complete(StatusCodes.OK, sql.insecureSql(username, password))(jsonMarshaller)
            }
          } ~
            path("test_secure") {
              paramOrFormFields("username", "password") { (username, password) =>
                complete(StatusCodes.OK, sql.secureSql(username, password))(jsonMarshaller)
              }
            }
        }
      } ~
      pathPrefix("ldapi") {
        post {
          path("test_insecure") {
            paramOrFormFields("username", "password") { (username, password) =>
              complete(ldap.injection(username, password))
            }
          } ~
            path("test_secure") {
              complete(ldap.secure)
            }
        }
      } ~
      path("cmdi" / "test_insecure") {
        post {
          paramOrFormField("cmd") { cmdParam =>
            complete(cmd.insecureCmd(cmdParam))
          }
        }
      } ~
      path("path_traversal" / "test_insecure") {
        post {
          paramOrFormField("path") { pathParam =>
            complete(path_.insecurePathTraversal(pathParam))
          }
        }
      } ~
      pathPrefix("source") {
        path("parameter" / "test") {
          formField("table") { table =>
            sql.insecureSql(table,
              (statement: Statement, query) => statement.executeQuery(query))
            complete(StatusCodes.OK, s"Request Parameters => source: $table");
          }
        } ~
          path("parametername" / "test") {
            formFieldMap { fm =>
              val table = fm.head._1
              sql.insecureSql(table,
                (statement: Statement, query) => statement.executeQuery(query))
              complete(StatusCodes.OK, s"Request Parameter Names => ${fm.keys}")
            }
          } ~
          path("headername" / "test") {
            extractRequest { req =>
              val source = req.headers.find(_.is("user"))
              if (source.isEmpty) {
                complete(StatusCodes.BadRequest, "No header named 'user'")
              } else {
                sql.insecureSql(source.get.name(),
                  (statement: Statement, query) => statement.executeQuery(query))
                complete(StatusCodes.OK, s"Request Headers => ${req.headers.map(_.name())}")
              }
            }
          } ~
          path("header" / "test") {
            headerValueByName("table") { headerValue =>
              sql.insecureSql(headerValue,
                (statement: Statement, query) => statement.executeQuery(query))
              complete(StatusCodes.OK, s"Request Header => $headerValue")
            }
          } ~
          path("cookiename" / "test") {
            extractRequest { r =>
              val maybeCookiePair = r.cookies.find(_.name.equals("user"))
              if (maybeCookiePair.isEmpty) {
                complete(StatusCodes.BadRequest, "No cookie named 'user'")
              } else {
                val c = maybeCookiePair.get
                sql.insecureSql(c.name,
                  (statement: Statement, query) => statement.executeQuery(query))
                complete(StatusCodes.OK, s"Request Cookie => $c")
              }
            }
          } ~
          path("cookievalue" / "test") {
            cookie("table") { c =>
              sql.insecureSql(c.value,
                (statement: Statement, query) => statement.executeQuery(query))
              complete(StatusCodes.OK, s"Request Cookie => $c")
            }
          } ~
          path("body" / "test") {
            post {
              entity(as[java.util.Map[String, Object]]) { map =>
                val name = map.get("name")
                val value = map.get("value")
                sql.insecureSql(name.asInstanceOf[String],
                  (statement: Statement, query) => statement.executeQuery(query))
                complete(StatusCodes.OK, s"@RequestBody to Test bean -> name: $name, value: $value")
              }
            }
          }
      }
  }

  private val jsonMarshaller : Marshaller[Object, RequestEntity] =
    Jackson.marshaller().asScala.map(_.asInstanceOf[RequestEntity] /* just downcast */)

  implicit val mapJsonUnmarshaller : Unmarshaller[HttpEntity, java.util.Map[String, Object]] =
    Jackson.unmarshaller(classOf[java.util.Map[String, Object]]).asScala

  private def paramOrFormField(p: String) = {
    parameter(p) | formField(p)
  }

  private def paramOrFormFields(p1: String, p2: String) = {
    parameters(p1, p2) | formFields(p1, p2)
  }
}
