#pragma once

#include <datadog/cerr_logger.h>
#include <datadog/span.h>
#include <datadog/tracer.h>

#include "scheduler.h"
#include "test_proto3_optional/apm_test_client.grpc.pb.h"

class TracingService final : public APMClient::Service {
public:
  TracingService(std::shared_ptr<datadog::tracing::CerrLogger> logger, std::unique_ptr<datadog::tracing::Tracer> tracer, std::shared_ptr<ManualScheduler> event_scheduler);
  virtual ~TracingService();
  virtual ::grpc::Status StartSpan(::grpc::ServerContext* /* context */, const ::StartSpanArgs* request, ::StartSpanReturn* response);
  virtual ::grpc::Status FinishSpan(::grpc::ServerContext* /* context */, const ::FinishSpanArgs* request, ::FinishSpanReturn* response);
  virtual ::grpc::Status SpanSetMeta(::grpc::ServerContext* /* context */, const ::SpanSetMetaArgs* request, ::SpanSetMetaReturn* response);
  virtual ::grpc::Status SpanSetMetric(::grpc::ServerContext* /* context */, const ::SpanSetMetricArgs* request, ::SpanSetMetricReturn* response);
  virtual ::grpc::Status SpanSetError(::grpc::ServerContext* /* context */, const ::SpanSetErrorArgs* request, ::SpanSetErrorReturn* response);
  virtual ::grpc::Status InjectHeaders(::grpc::ServerContext* /* context */, const ::InjectHeadersArgs* request, ::InjectHeadersReturn* response);
  virtual ::grpc::Status FlushSpans(::grpc::ServerContext* /* context */, const ::FlushSpansArgs* request, ::FlushSpansReturn* response);
  virtual ::grpc::Status FlushTraceStats(::grpc::ServerContext* /* context */, const ::FlushTraceStatsArgs* request, ::FlushTraceStatsReturn* response);
  virtual ::grpc::Status StopTracer(::grpc::ServerContext* /* context */, const ::StopTracerArgs* request, ::StopTracerReturn* response);

private:
  std::shared_ptr<datadog::tracing::CerrLogger> logger_;
  std::unique_ptr<datadog::tracing::Tracer> tracer_;
  std::shared_ptr<ManualScheduler> event_scheduler_;
  std::unordered_map<uint64_t, datadog::tracing::Span> active_spans_;
};
