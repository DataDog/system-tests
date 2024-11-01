#include "tracing_service.h"
#include <datadog/span_config.h>
#include "distributed_headers_dicts.h"

TracingService::TracingService(std::shared_ptr<DeveloperNoiseLogger> logger, std::unique_ptr<datadog::tracing::Tracer> tracer, std::shared_ptr<ManualScheduler> event_scheduler)
  : logger_(logger), tracer_(std::move(tracer)), event_scheduler_(event_scheduler) {}

void TracingService::onRequest(const Pistache::Http::Request& request, Pistache::Http::ResponseWriter response) {
  // Determine the request path and method to call the appropriate handler
  auto path = request.resource();
  if (path == "/start_span" && request.method() == Pistache::Http::Method::Post) {
    handleStartSpan(request, std::move(response));
  } else if (path == "/finish_span" && request.method() == Pistache::Http::Method::Post) {
    handleFinishSpan(request, std::move(response));
  } else if (path == "/span_set_meta" && request.method() == Pistache::Http::Method::Post) {
    handleSpanSetMeta(request, std::move(response));
  } else if (path == "/span_set_metric" && request.method() == Pistache::Http::Method::Post) {
    handleSpanSetMetric(request, std::move(response));
  } else if (path == "/span_set_error" && request.method() == Pistache::Http::Method::Post) {
    handleSpanSetError(request, std::move(response));
  } else if (path == "/inject_headers" && request.method() == Pistache::Http::Method::Post) {
    handleInjectHeaders(request, std::move(response));
  } else if (path == "/flush_spans" && request.method() == Pistache::Http::Method::Post) {
    handleFlushSpans(request, std::move(response));
  } else if (path == "/flush_trace_stats" && request.method() == Pistache::Http::Method::Post) {
    handleFlushTraceStats(request, std::move(response));
  } else if (path == "/stop_tracer" && request.method() == Pistache::Http::Method::Post) {
    handleStopTracer(request, std::move(response));
  } else {
    response.send(Pistache::Http::Code::Not_Found, "Not Found");
  }
}

void TracingService::handleStartSpan(const Pistache::Http::Request& request, Pistache::Http::ResponseWriter response) {
  // Deserialize the request body into StartSpanArgs structure
  StartSpanArgs args;
  // Assume there's a function to parse JSON or similar
  if (!parseRequestBody(request.body(), args)) {
    response.send(Pistache::Http::Code::Bad_Request, "Invalid request");
    return;
  }

  logger_->log_info("StartSpan:");
  logger_->log_info("  name: " + args.name());
  // Log other fields similarly...

  // Set up the SpanConfig based on the request args
  datadog::tracing::SpanConfig config;
  // Fill config based on args...

  // Create span and respond
  // Logic to create span similar to the original implementation
  auto span = tracer_->create_span(config);
  
  // Create response structure
  StartSpanReturn startSpanReturn;
  startSpanReturn.set_trace_id(span.trace_id().low);
  startSpanReturn.set_span_id(span.id());

  // Respond with the trace ID and span ID
  response.send(Pistache::Http::Code::Ok, startSpanReturn.SerializeAsString());
}

void TracingService::handleFinishSpan(const Pistache::Http::Request& request, Pistache::Http::ResponseWriter response) {
  FinishSpanArgs args;
  if (!parseRequestBody(request.body(), args)) {
    response.send(Pistache::Http::Code::Bad_Request, "Invalid request");
    return;
  }

  logger_->log_info("FinishSpan:");
  logger_->log_info("  id: " + std::to_string(args.id()));

  auto span_id = args.id();
  // Logic to finish span
  // Erase the span from active_spans_
  
  response.send(Pistache::Http::Code::Ok, "");
}

// Implement other handlers similarly...

void TracingService::handleSpanSetMeta(const Pistache::Http::Request& request, Pistache::Http::ResponseWriter response) {
  SpanSetMetaArgs args;
  if (!parseRequestBody(request.body(), args)) {
    response.send(Pistache::Http::Code::Bad_Request, "Invalid request");
    return;
  }

  // Similar logic as before to set metadata on the span
  auto span_id = args.span_id();
  // Retrieve and update span...

  response.send(Pistache::Http::Code::Ok, "");
}

void TracingService::handleSpanSetMetric(const Pistache::Http::Request& request, Pistache::Http::ResponseWriter response) {
  // No direct method to set a span metric.
  response.send(Pistache::Http::Code::Ok, "OK");
}

void TracingService::handleSpanSetError(const Pistache::Http::Request& request, Pistache::Http::ResponseWriter response) {
  SpanSetErrorArgs args;
  if (!parseRequestBody(request.body(), args)) {
    response.send(Pistache::Http::Code::Bad_Request, "Invalid request");
    return;
  }

  auto span_id = args.span_id();
  auto found = active_spans_.find(span_id);
  if (found == active_spans_.end()) {
    logger_->log_info("TracingService::SpanSetError: span not found for id " + std::to_string(span_id));
    response.send(Pistache::Http::Code::Internal_Server_Error, "no active span for id " + std::to_string(span_id));
    return;
  }
  auto& span = found->second;

  if (args.has_type() && !args.type().empty()) {
    span.set_error_type(args.type());
  }
  if (args.has_message() && !args.message().empty()) {
    span.set_error_message(args.message());
  }
  if (args.has_stack() && !args.stack().empty()) {
    span.set_error_stack(args.stack());
  }

  response.send(Pistache::Http::Code::Ok, "");
}

void TracingService::handleInjectHeaders(const Pistache::Http::Request& request, Pistache::Http::ResponseWriter response) {
  InjectHeadersArgs args;
  if (!parseRequestBody(request.body(), args)) {
    response.send(Pistache::Http::Code::Bad_Request, "Invalid request");
    return;
  }

  logger_->log_info("InjectHeaders");
  auto span_id = args.span_id();
  auto found = active_spans_.find(span_id);
  if (found == active_spans_.end()) {
    logger_->log_info("TracingService::InjectHeaders: span not found for id " + std::to_string(span_id));
    response.send(Pistache::Http::Code::Internal_Server_Error, "no active span for id " + std::to_string(span_id));
    return;
  }
  const auto& span = found->second;

  // Prepare headers for injection
  auto headers_writer = DistributedHTTPHeadersWriter(response.mutable_http_headers());
  span.inject(headers_writer);
  logger_->log_info("  http_headers:");
  auto& headers = response.http_headers();
  for (int i = 0; i < headers.http_headers_size(); i++) {
    logger_->log_info("  " + headers.http_headers(i).key() + ":" + headers.http_headers(i).value());
  }

  response.send(Pistache::Http::Code::Ok, "");
}

void TracingService::handleFlushSpans(const Pistache::Http::Request& request, Pistache::Http::ResponseWriter response) {
  event_scheduler_->flush_traces();
  response.send(Pistache::Http::Code::Ok, "");
}

void TracingService::handleFlushTraceStats(const Pistache::Http::Request& request, Pistache::Http::ResponseWriter response) {
  // Placeholder for testing, returning OK
  response.send(Pistache::Http::Code::Ok, "");
}

void TracingService::handleStopTracer(const Pistache::Http::Request& request, Pistache::Http::ResponseWriter response) {
  // Placeholder for testing, returning UNIMPLEMENTED
  response.send(Pistache::Http::Code::Not_Implemented, "Not Implemented");
}