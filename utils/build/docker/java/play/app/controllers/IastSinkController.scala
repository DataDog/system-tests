package controllers

import com.datadoghq.system_tests.iast.utils.CmdExamples
import play.api.mvc._

import javax.inject.{Inject, Singleton}

@Singleton
class IastSinkController @Inject()(cc: MessagesControllerComponents) extends AbstractController(cc) {

  private val cmdExamples = new CmdExamples()

  def cmdiInsecure = Action { request =>
    val cmd = request.body.asFormUrlEncoded.flatMap(_.get("cmd")).map(_.head).getOrElse("")
    val result = cmdExamples.insecureCmd(cmd)
    Ok(result)
  }

  def cmdiSecure = Action { request =>
    Ok("Command executed: ls")
  }
} 