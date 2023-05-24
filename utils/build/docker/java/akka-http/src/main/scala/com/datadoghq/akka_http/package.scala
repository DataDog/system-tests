package com.datadoghq

import akka.actor.ActorSystem
import akka.stream.SystemMaterializer
import io.opentracing.Tracer
import io.opentracing.util.GlobalTracer

package object akka_http {
  val tracer : Tracer = GlobalTracer.get()

  implicit val system = ActorSystem("my-system")
  implicit val materializer = SystemMaterializer.get(system).materializer
  implicit val executionContext = system.dispatcher
}
