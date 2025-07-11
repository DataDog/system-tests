package com.datadoghq.akka_http

import akka.http.scaladsl.model.StatusCodes
import akka.http.scaladsl.server.Directives._
import akka.http.scaladsl.server.Route
import com.datadoghq.akka_http.Resources.{dataSource, ldapContext}
import com.datadoghq.system_tests.iast.utils._

import java.sql.Statement

object IastRoutes {

  private val superSecretAccessKey = "insecure"
  private val cmd = new CmdExamples()
  private val crypto = new CryptoExamples()
  private val ldap = new LDAPExamples(ldapContext)
  private val path_ = new PathExamples()
  private val sql = new SqlExamples(dataSource)
  private val xpath = new XPathExamples()
  private val random = new WeakRandomnessExamples()

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
      pathPrefix("xpathi") {
              post {
                path("test_insecure") {
                  paramOrFormField("expression") { expression =>
                    xpath.insecureXPath(expression)
                    complete(StatusCodes.OK, "Insecure")
                  }
                } ~
                  path("test_secure") {
                    xpath.secureXPath()
                    complete(StatusCodes.OK, "Secure")
                  }
              }
            } ~
      pathPrefix("weak_randomness") {
        get {
          path("test_insecure") {
            complete(StatusCodes.OK, random.weakRandom())
          } ~
            path("test_secure") {
              complete(StatusCodes.OK, random.secureRandom())
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
          post {
            formField("table") { table =>
              sql.insecureSql(table,
                (statement: Statement, query) => statement.executeQuery(query))
              complete(StatusCodes.OK, s"Request Parameters => source: $table");
            }
          } ~
            get {
              paramOrFormField("table") { table =>
                sql.insecureSql(table,
                  (statement: Statement, query) => statement.executeQuery(query))
                complete(StatusCodes.OK, s"Request Parameters => source: $table");
              }
            }
        } ~
          path("parametername" / "test") {
            post {
              formFieldMap { fm =>
                val table = fm.head._1
                sql.insecureSql(table,
                  (statement: Statement, query) => statement.executeQuery(query))
                complete(StatusCodes.OK, s"Request Parameter Names => ${fm.keys}")
              }
            } ~
              get {
                parameterMap { pm =>
                  val table = pm.head._1
                  sql.insecureSql(table,
                    (statement: Statement, query) => statement.executeQuery(query))
                  complete(StatusCodes.OK, s"Request Parameter Names => ${pm.keys}")
                }
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
              val maybeCookiePair = r.cookies.find(_.name.equals("table"))
              if (maybeCookiePair.isEmpty) {
                complete(StatusCodes.BadRequest, "No cookie named 'table'")
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
      } ~
      pathPrefix("sc") {
        pathPrefix("s") {
          post {
            path("configured") {
              formField("param") { param =>
                val sanitized = SecurityControlUtil.sanitize(param)
                cmd.insecureCmd(sanitized)
                complete(StatusCodes.OK)
              }
            } ~
              path("not-configured") {
                formField("param") { param =>
                  val sanitized = SecurityControlUtil.sanitize(param)
                  complete(StatusCodes.OK, sql.insecureSql(sanitized, "password"))(jsonMarshaller)
                }
              } ~
              path("all") {
                formField("param") { param =>
                  val sanitized = SecurityControlUtil.sanitizeForAllVulns(param)
                  complete(StatusCodes.OK, sql.insecureSql(sanitized, "password"))(jsonMarshaller)
                }
              } ~
              pathPrefix("overloaded") {
                path("secure") {
                  formField("param") { param =>
                    val sanitized = SecurityControlUtil.overloadedSanitize(param)
                    cmd.insecureCmd(sanitized)
                    complete(StatusCodes.OK)
                  }
                } ~
                  path("insecure") {
                    formField("param") { param =>
                      val sanitized = SecurityControlUtil.overloadedSanitize(param, null)
                      cmd.insecureCmd(sanitized)
                      complete(StatusCodes.OK)
                    }
                  }
              }
          }
        } ~
          pathPrefix("iv") {
            post {
              path("configured") {
                formField("param") { param =>
                  if (SecurityControlUtil.validate(param)) {
                    cmd.insecureCmd(param)
                  }
                  complete(StatusCodes.OK)
                }
              } ~
                path("not-configured") {
                  formField("param") { param =>
                    if (SecurityControlUtil.validate(param)) {
                      sql.insecureSql(param, "password")
                    }
                    complete(StatusCodes.OK)
                  }
                } ~
                path("all") {
                  formField("param") { param =>
                    if (SecurityControlUtil.validateForAllVulns(param)) {
                      sql.insecureSql(param, "password")
                    }
                    complete(StatusCodes.OK)
                  }
                } ~
                pathPrefix("overloaded") {
                  path("secure") {
                    formFields("user", "password") { (user, pass) =>
                      if (SecurityControlUtil.overloadedValidation(null, user, pass)) {
                        sql.insecureSql(user, pass)
                      }
                      complete(StatusCodes.OK)
                    }
                  } ~
                    path("insecure") {
                      formFields("user", "password") { (user, pass) =>
                        if (SecurityControlUtil.overloadedValidation(user, pass)) {
                          sql.insecureSql(user, pass)
                        }
                        complete(StatusCodes.OK)
                      }
                    }
                }
            }
          }
      } ~
      path("sampling-by-route-method-count" / Segment) { id =>
        get {
          try {
            java.security.MessageDigest.getInstance("SHA1").digest("hash1".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            java.security.MessageDigest.getInstance("SHA1").digest("hash2".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            java.security.MessageDigest.getInstance("SHA1").digest("hash3".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            java.security.MessageDigest.getInstance("SHA1").digest("hash4".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            java.security.MessageDigest.getInstance("SHA1").digest("hash5".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            java.security.MessageDigest.getInstance("SHA1").digest("hash6".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            java.security.MessageDigest.getInstance("SHA1").digest("hash7".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            java.security.MessageDigest.getInstance("SHA1").digest("hash8".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            java.security.MessageDigest.getInstance("SHA1").digest("hash9".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            java.security.MessageDigest.getInstance("SHA1").digest("hash10".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            java.security.MessageDigest.getInstance("SHA1").digest("hash11".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            java.security.MessageDigest.getInstance("SHA1").digest("hash12".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            java.security.MessageDigest.getInstance("SHA1").digest("hash13".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            java.security.MessageDigest.getInstance("SHA1").digest("hash14".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            java.security.MessageDigest.getInstance("SHA1").digest("hash15".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            complete("ok")
          } catch {
            case e: Exception => complete(StatusCodes.InternalServerError, e.getMessage)
          }
        } ~
          post {
            try {
              java.security.MessageDigest.getInstance("SHA1").digest("hash1".getBytes(java.nio.charset.StandardCharsets.UTF_8))
              java.security.MessageDigest.getInstance("SHA1").digest("hash2".getBytes(java.nio.charset.StandardCharsets.UTF_8))
              java.security.MessageDigest.getInstance("SHA1").digest("hash3".getBytes(java.nio.charset.StandardCharsets.UTF_8))
              java.security.MessageDigest.getInstance("SHA1").digest("hash4".getBytes(java.nio.charset.StandardCharsets.UTF_8))
              java.security.MessageDigest.getInstance("SHA1").digest("hash5".getBytes(java.nio.charset.StandardCharsets.UTF_8))
              java.security.MessageDigest.getInstance("SHA1").digest("hash6".getBytes(java.nio.charset.StandardCharsets.UTF_8))
              java.security.MessageDigest.getInstance("SHA1").digest("hash7".getBytes(java.nio.charset.StandardCharsets.UTF_8))
              java.security.MessageDigest.getInstance("SHA1").digest("hash8".getBytes(java.nio.charset.StandardCharsets.UTF_8))
              java.security.MessageDigest.getInstance("SHA1").digest("hash9".getBytes(java.nio.charset.StandardCharsets.UTF_8))
              java.security.MessageDigest.getInstance("SHA1").digest("hash10".getBytes(java.nio.charset.StandardCharsets.UTF_8))
              java.security.MessageDigest.getInstance("SHA1").digest("hash11".getBytes(java.nio.charset.StandardCharsets.UTF_8))
              java.security.MessageDigest.getInstance("SHA1").digest("hash12".getBytes(java.nio.charset.StandardCharsets.UTF_8))
              java.security.MessageDigest.getInstance("SHA1").digest("hash13".getBytes(java.nio.charset.StandardCharsets.UTF_8))
              java.security.MessageDigest.getInstance("SHA1").digest("hash14".getBytes(java.nio.charset.StandardCharsets.UTF_8))
              java.security.MessageDigest.getInstance("SHA1").digest("hash15".getBytes(java.nio.charset.StandardCharsets.UTF_8))
              complete("ok")
            } catch {
              case e: Exception => complete(StatusCodes.InternalServerError, e.getMessage)
            }
          }
      } ~
      path("sampling-by-route-method-count-2" / Segment) { id =>
        get {
          try {
            java.security.MessageDigest.getInstance("SHA1").digest("hash1".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            java.security.MessageDigest.getInstance("SHA1").digest("hash2".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            java.security.MessageDigest.getInstance("SHA1").digest("hash3".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            java.security.MessageDigest.getInstance("SHA1").digest("hash4".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            java.security.MessageDigest.getInstance("SHA1").digest("hash5".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            java.security.MessageDigest.getInstance("SHA1").digest("hash6".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            java.security.MessageDigest.getInstance("SHA1").digest("hash7".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            java.security.MessageDigest.getInstance("SHA1").digest("hash8".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            java.security.MessageDigest.getInstance("SHA1").digest("hash9".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            java.security.MessageDigest.getInstance("SHA1").digest("hash10".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            java.security.MessageDigest.getInstance("SHA1").digest("hash11".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            java.security.MessageDigest.getInstance("SHA1").digest("hash12".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            java.security.MessageDigest.getInstance("SHA1").digest("hash13".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            java.security.MessageDigest.getInstance("SHA1").digest("hash14".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            java.security.MessageDigest.getInstance("SHA1").digest("hash15".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            complete("ok")
          } catch {
            case e: Exception => complete(StatusCodes.InternalServerError, e.getMessage)
          }
        }
      }
  }

  private def paramOrFormField(p: String) = {
    parameter(p) | formField(p)
  }

  private def paramOrFormFields(p1: String, p2: String) = {
    parameters(p1, p2) | formFields(p1, p2)
  }
}
