import datadog.trace.api.interceptor.MutableSpan
import io.opentracing.util.GlobalTracer
import io.opentracing.{Span, Tracer}

package object controllers {
  val tracer : Tracer = GlobalTracer.get()
  val eventTracker = datadog.trace.api.GlobalTracer.getEventTracker

  def withSpan[A](span: Span)(f: => A): A = try f finally span.finish()

  def setRootSpanTag(key: String, value: String): Unit = {
    val span = tracer.activeSpan
    if (span.isInstanceOf[MutableSpan]) {
      val rootSpan = span.asInstanceOf[MutableSpan].getLocalRootSpan
      if (rootSpan != null) rootSpan.setTag(key, value)
    }
  }
}
