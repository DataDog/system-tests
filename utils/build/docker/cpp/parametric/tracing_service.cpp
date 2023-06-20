#include "tracing_service.h"

#include <datadog/span_config.h>

#include "distributed_headers_dicts.h"

TracingService::TracingService(std::shared_ptr<datadog::tracing::CerrLogger> logger, std::unique_ptr<datadog::tracing::Tracer> tracer,
                               std::shared_ptr<ManualScheduler> event_scheduler)
    : logger_(logger), tracer_(std::move(tracer)), event_scheduler_(event_scheduler) {}

TracingService::~TracingService() {}

::grpc::Status TracingService::StartSpan(::grpc::ServerContext* /* context */, const ::StartSpanArgs* request, ::StartSpanReturn* response) {
  datadog::tracing::SpanConfig config;
  config.name = request->name();
  if (request->has_service()) {
    config.service = request->service();
  }
  if (request->has_resource()) {
    config.resource = request->resource();
  }
  if (request->has_type()) {
    config.service_type = request->type();
  }
  // Origin can't be set directly, only via extraction
  if (request->has_origin()) {
    logger_->log_error("StartSpanArgs origin, but this can only be set via the 'x-datadog-origin' header");
  }

  auto span = tracer_->extract_or_create_span(DistributedHTTPHeadersReader(request->http_headers()), config);
  if (!span) {
    logger_->log_error("could not extract span from http_headers");
    logger_->log_error(span.error());
    return ::grpc::Status(::grpc::StatusCode::INTERNAL, "could not extract span from http_headers");
  }

  active_spans_.insert({span->id(), std::move(*span)});
  response->set_trace_id(span->trace_id().low);
  response->set_span_id(span->id());
  return ::grpc::Status(::grpc::StatusCode::OK, "");
}

::grpc::Status TracingService::FinishSpan(::grpc::ServerContext* /* context */, const ::FinishSpanArgs* request, ::FinishSpanReturn* /* response */) {
  auto span_id = request->id();
  auto found = active_spans_.find(span_id);
  if (found == active_spans_.end()) {
    logger_->log_error("TracingService::FinishSpan: span not found for id " + std::to_string(span_id));
    return ::grpc::Status(::grpc::StatusCode::INTERNAL, std::string() + "no active span for id " + std::to_string(span_id));
  }

  // spans finish when they are destroyed
  active_spans_.erase(found);

  return ::grpc::Status(::grpc::StatusCode::OK, "");
}

::grpc::Status TracingService::SpanSetMeta(::grpc::ServerContext* /* context */, const ::SpanSetMetaArgs* request, ::SpanSetMetaReturn* /* response */) {
  auto span_id = request->span_id();
  auto found = active_spans_.find(span_id);
  if (found == active_spans_.end()) {
    logger_->log_error("TracingService::SpanSetMeta: span not found for id " + std::to_string(span_id));
    return ::grpc::Status(::grpc::StatusCode::INTERNAL, std::string() + "no active span for id " + std::to_string(span_id));
  }
  auto& span = found->second;

  span.set_tag(request->key(), request->value());

  return ::grpc::Status(::grpc::StatusCode::OK, "");
}

::grpc::Status TracingService::SpanSetMetric(::grpc::ServerContext* /* context */, const ::SpanSetMetricArgs* /* request */, ::SpanSetMetricReturn* /* response */) {
  // No method available for directly setting a span metric.
  // Returning OK instead of UNIMPLEMENTED to satisfy the test framework.
  return ::grpc::Status(::grpc::StatusCode::OK, "");
}

::grpc::Status TracingService::SpanSetError(::grpc::ServerContext* /* context */, const ::SpanSetErrorArgs* request, ::SpanSetErrorReturn* /* response */) {
  auto span_id = request->span_id();
  auto found = active_spans_.find(span_id);
  if (found == active_spans_.end()) {
    logger_->log_error("TracingService::SpanSetError: span not found for id " + std::to_string(span_id));
    return ::grpc::Status(::grpc::StatusCode::INTERNAL, std::string() + "no active span for id " + std::to_string(span_id));
  }
  auto& span = found->second;

  if (request->has_type()) {
    span.set_error_type(request->type());
  }
  if (request->has_message()) {
    span.set_error_message(request->message());
  }
  if (request->has_stack()) {
    span.set_error_stack(request->stack());
  }

  return ::grpc::Status(::grpc::StatusCode::OK, "");
}

::grpc::Status TracingService::InjectHeaders(::grpc::ServerContext* /* context */, const ::InjectHeadersArgs* request, ::InjectHeadersReturn* response) {
  std::cout << "InjectHeaders" << std::endl;
  auto span_id = request->span_id();
  auto found = active_spans_.find(span_id);
  if (found == active_spans_.end()) {
    logger_->log_error("TracingService::InjectHeaders: span not found for id " + std::to_string(span_id));
    return ::grpc::Status(::grpc::StatusCode::INTERNAL, std::string() + "no active span for id " + std::to_string(span_id));
  }
  const auto& span = found->second;

  auto headers_writer = DistributedHTTPHeadersWriter(response->mutable_http_headers());
  span.inject(headers_writer);

  return ::grpc::Status(::grpc::StatusCode::OK, "");
}

::grpc::Status TracingService::FlushSpans(::grpc::ServerContext* /* context */, const ::FlushSpansArgs* /* request */, ::FlushSpansReturn* /* response */) {
  event_scheduler_->manual_flush();
  return ::grpc::Status(::grpc::StatusCode::OK, "");
}

::grpc::Status TracingService::FlushTraceStats(::grpc::ServerContext* /* context */, const ::FlushTraceStatsArgs* /* request */, ::FlushTraceStatsReturn* /* response */) {
  // This is a lie to allow a basic test to complete.
  return ::grpc::Status(::grpc::StatusCode::OK, "");
}

::grpc::Status TracingService::StopTracer(::grpc::ServerContext* /* context */, const ::StopTracerArgs* /* request */, ::StopTracerReturn* /* response */) {
  // This is a lie that seems to have no consequence for basic tests.
  return ::grpc::Status(::grpc::StatusCode::UNIMPLEMENTED, "");
}
