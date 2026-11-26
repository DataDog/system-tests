package controllers

import play.api.mvc._

import javax.inject.{Inject, Singleton}

// Routes for the RFC-1125 normalized route tests (tests/appsec/api_security_testing/test_normalized_route.py),
// declared in conf/routes. Only the declared paths matter: the actions ignore their parameters.
@Singleton
class NormalizedRouteController @Inject()(cc: ControllerComponents) extends AbstractController(cc) {

  def noParam = Action(Ok("ok"))

  def oneParam(a: String) = Action(Ok("ok"))

  def twoParams(a: String, b: String) = Action(Ok("ok"))

  def threeParams(a: String, b: String, c: String) = Action(Ok("ok"))
}
