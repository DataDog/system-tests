package com.datadoghq

import akka.actor.ActorSystem
import akka.http.javadsl.marshallers.jackson.Jackson
import akka.http.scaladsl.marshalling.Marshaller
import akka.http.scaladsl.model.{HttpEntity, MediaTypes, RequestEntity}
import akka.http.scaladsl.unmarshalling.Unmarshaller
import akka.stream.SystemMaterializer
import com.fasterxml.jackson.databind.MapperFeature
import com.fasterxml.jackson.databind.json.JsonMapper
import com.fasterxml.jackson.module.scala.{DefaultScalaModule, ScalaObjectMapper}
import datadog.trace.api.interceptor.MutableSpan
import io.opentracing.{Span, Tracer}
import io.opentracing.util.GlobalTracer

package object akka_http {
  val tracer : Tracer = GlobalTracer.get()
  val eventTracker = datadog.trace.api.GlobalTracer.getEventTracker

  implicit val system = ActorSystem("my-system")
  implicit val materializer = SystemMaterializer.get(system).materializer
  implicit val executionContext = system.dispatcher

  implicit def withSpan[A](span: Span)(f: => A): A = try f finally span.finish()

  implicit def setRootSpanTag(key: String, value: String): Unit = {
    val span = tracer.activeSpan
    if (span.isInstanceOf[MutableSpan]) {
      val rootSpan = span.asInstanceOf[MutableSpan].getLocalRootSpan
      if (rootSpan != null) rootSpan.setTag(key, value)
    }
  }

  implicit val mapJsonUnmarshaller : Unmarshaller[HttpEntity, java.util.Map[String, Object]] =
    Jackson.unmarshaller(classOf[java.util.Map[String, Object]])
      .asScala
      .forContentTypes(MediaTypes.`application/json`)

  val generalizedJsonUnmarshaller : Unmarshaller[HttpEntity, Object] = {
    Jackson.unmarshaller(classOf[Object])
      .asScala
      .forContentTypes(MediaTypes.`application/json`)
  }

  private val jsonMapper: JsonMapper =
    JsonMapper.builder.enable(MapperFeature.SORT_PROPERTIES_ALPHABETICALLY)
      .addModule(DefaultScalaModule)
      .build

  val jsonMarshaller : Marshaller[Object, RequestEntity] =
    Jackson.marshaller(jsonMapper).asScala.map(_.asInstanceOf[RequestEntity] /* just downcast */)

}
