package controllers

import com.datadoghq.system_tests.iast.utils.SqlExamples
import play.api.mvc._
import resources.Resources

import javax.inject.{Inject, Singleton}

@Singleton
class IastSourceController @Inject()(cc: MessagesControllerComponents, res: Resources) extends AbstractController(cc) {

  private val sql = new SqlExamples(res.dataSource)

  def sourceParameterGet = Action { request =>
    val table = request.queryString.get("table").map(_.head).getOrElse("")
    sql.insecureSql(table, (statement, query) => statement.executeQuery(query))
    Ok(s"Request Parameters => source: $table")
  }

  def sourceParameterPost = Action { request =>
    val table = request.body.asFormUrlEncoded.flatMap(_.get("table")).map(_.head).getOrElse("")
    sql.insecureSql(table, (statement, query) => statement.executeQuery(query))
    Ok(s"Request Parameters => source: $table")
  }
}