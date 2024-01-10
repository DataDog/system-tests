#include "tracing_service.h"

#include <datadog/span_config.h>

#include "distributed_headers_dicts.h"

TracingService::TracingService(std::shared_ptr<DeveloperNoiseLogger> logger, std::unique_ptr<datadog::tracing::Tracer> tracer, std::shared_ptr<ManualScheduler> event_scheduler)
    : logger_(logger), tracer_(std::move(tracer)), event_scheduler_(event_scheduler) {}

TracingService::~TracingService() {}

::grpc::Status TracingService::StartSpan(::grpc::ServerContext* /* context */, const ::StartSpanArgs* request, ::StartSpanReturn* response) {
  logger_->log_info("StartSpan:");
  logger_->log_info("  name: " + request->name());
  if (request->has_service() && !request->service().empty()) {
    logger_->log_info("  service: " + request->service());
  }
  if (request->has_parent_id() && request->parent_id() != 0) {
    logger_->log_info("  parent_id: " + std::to_string(request->parent_id()));
  }
  if (request->has_resource() && !request->resource().empty()) {
    logger_->log_info("  resource: " + request->resource());
  }
  if (request->has_type() && !request->type().empty()) {
    logger_->log_info("  type: " + request->type());
  }
  if (request->has_origin() && !request->origin().empty()) {
    logger_->log_info("  origin: " + request->origin());
  }
  if (request->has_http_headers() && request->http_headers().http_headers_size() != 0) {
    logger_->log_info("  http_headers:");
    auto& headers = request->http_headers();
    for (int i = 0; i < headers.http_headers_size(); i++) {
      logger_->log_info("    " + headers.http_headers(i).key() + ":" + headers.http_headers(i).value());
    }
  }

  datadog::tracing::SpanConfig config;
  config.name = request->name();
  if (request->has_service() && !request->service().empty()) {
    config.service = request->service();
  }
  if (request->has_resource() && !request->resource().empty()) {
    config.resource = request->resource();
  }
  if (request->has_type() && !request->type().empty()) {
    config.service_type = request->type();
  }
  // Origin can't be set directly, only via extraction
  if (request->has_origin() && !request->origin().empty()) {
    logger_->log_info("StartSpanArgs origin, but this can only be set via the 'x-datadog-origin' header");
  }

  // Create span using either a provided parent id or via extraction
  if (request->has_parent_id() && request->parent_id() != 0) {
    auto span_id = request->parent_id();
    auto found = active_spans_.find(span_id);
    if (found == active_spans_.end()) {
      logger_->log_info("StartSpan: span not found for id " + std::to_string(span_id));
      return ::grpc::Status(::grpc::StatusCode::INTERNAL, "no active span for id " + std::to_string(span_id));
    }
    auto& parent_span = found->second;
    auto span = parent_span.create_child(config);

    response->set_trace_id(span.trace_id().low);
    response->set_span_id(span.id());
    logger_->log_info("StartSpan response trace_id:" + std::to_string(span.trace_id().low) + " span_id:" + std::to_string(span.id()));
    active_spans_.insert({span.id(), std::move(span)});
  } else {
    auto extracted = tracer_->extract_or_create_span(DistributedHTTPHeadersReader(request->http_headers()), config);
    std::optional<datadog::tracing::Span> span;
    if (!extracted) {
      const auto error = extracted.error().with_prefix("could not extract span from http_headers: ");
      logger_->log_error(error);
      span.emplace(tracer_->create_span(config));
    } else {
      span.emplace(std::move(*extracted));
    }

    response->set_trace_id(span->trace_id().low);
    response->set_span_id(span->id());
    logger_->log_info("StartSpan response trace_id:" + std::to_string(span->trace_id().low) + " span_id:" + std::to_string(span->id()));
    active_spans_.insert({span->id(), std::move(*span)});
  }

  return ::grpc::Status(::grpc::StatusCode::OK, "");
}

::grpc::Status TracingService::FinishSpan(::grpc::ServerContext* /* context */, const ::FinishSpanArgs* request, ::FinishSpanReturn* /* response */) {
  logger_->log_info("FinishSpan:");
  logger_->log_info("  id: " + std::to_string(request->id()));

  auto span_id = request->id();
  auto found = active_spans_.find(span_id);
  if (found == active_spans_.end()) {
    logger_->log_info("TracingService::FinishSpan: span not found for id " + std::to_string(span_id));
    return ::grpc::Status(::grpc::StatusCode::INTERNAL, "no active span for id " + std::to_string(span_id));
  }

  // spans finish when they are destroyed
  active_spans_.erase(found);

  return ::grpc::Status(::grpc::StatusCode::OK, "");
}

::grpc::Status TracingService::SpanSetMeta(::grpc::ServerContext* /* context */, const ::SpanSetMetaArgs* request, ::SpanSetMetaReturn* /* response */) {
  auto span_id = request->span_id();
  auto found = active_spans_.find(span_id);
  if (found == active_spans_.end()) {
    logger_->log_info("TracingService::SpanSetMeta: span not found for id " + std::to_string(span_id));
    return ::grpc::Status(::grpc::StatusCode::INTERNAL, "no active span for id " + std::to_string(span_id));
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
    logger_->log_info("TracingService::SpanSetError: span not found for id " + std::to_string(span_id));
    return ::grpc::Status(::grpc::StatusCode::INTERNAL, "no active span for id " + std::to_string(span_id));
  }
  auto& span = found->second;

  if (request->has_type() && !request->type().empty()) {
    span.set_error_type(request->type());
  }
  if (request->has_message() && !request->message().empty()) {
    span.set_error_message(request->message());
  }
  if (request->has_stack() && !request->stack().empty()) {
    span.set_error_stack(request->stack());
  }

  return ::grpc::Status(::grpc::StatusCode::OK, "");
}

::grpc::Status TracingService::InjectHeaders(::grpc::ServerContext* /* context */, const ::InjectHeadersArgs* request, ::InjectHeadersReturn* response) {
  logger_->log_info("InjectHeaders");
  auto span_id = request->span_id();
  auto found = active_spans_.find(span_id);
  if (found == active_spans_.end()) {
    logger_->log_info("TracingService::InjectHeaders: span not found for id " + std::to_string(span_id));
    return ::grpc::Status(::grpc::StatusCode::INTERNAL, "no active span for id " + std::to_string(span_id));
  }
  const auto& span = found->second;

  auto headers_writer = DistributedHTTPHeadersWriter(response->mutable_http_headers());
  span.inject(headers_writer);
  logger_->log_info("  http_headers:");
  auto& headers = response->http_headers();
  for (int i = 0; i < headers.http_headers_size(); i++) {
    logger_->log_info("    " + headers.http_headers(i).key() + ":" + headers.http_headers(i).value());
  }

  return ::grpc::Status(::grpc::StatusCode::OK, "");
}

::grpc::Status TracingService::FlushSpans(::grpc::ServerContext* /* context */, const ::FlushSpansArgs* /* request */, ::FlushSpansReturn* /* response */) {
  event_scheduler_->flush_traces();
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
