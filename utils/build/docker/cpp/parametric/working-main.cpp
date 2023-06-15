#include <datadog/dict_reader.h>
#include <datadog/dict_writer.h>
#include <datadog/event_scheduler.h>
#include <datadog/span_config.h>
#include <datadog/tracer.h>
#include <datadog/tracer_config.h>
#include <grpc/grpc.h>
#include <grpcpp/server_builder.h>
#include <test_proto3_optional/apm_test_client.grpc.pb.h>
#include <test_proto3_optional/apm_test_client.pb.h>

#include <chrono>
#include <cstdlib>
#include <datadog/json.hpp>
#include <iostream>
#include <thread>

class DistributedHTTPHeadersReader : public datadog::tracing::DictReader {
  const DistributedHTTPHeaders& headers_;

public:
  DistributedHTTPHeadersReader(const DistributedHTTPHeaders& headers) : headers_(headers) {}

  datadog::tracing::Optional<datadog::tracing::StringView> lookup(datadog::tracing::StringView key) const override {
    for (int i = 0; i < headers_.http_headers_size(); i++) {
      if (headers_.http_headers(i).key() == key) {
        return headers_.http_headers(i).value();
      }
    }
    return datadog::tracing::nullopt;
  }

  void visit(const std::function<void(datadog::tracing::StringView key, datadog::tracing::StringView value)>& visitor) const override {
    for (int i = 0; i < headers_.http_headers_size(); i++) {
      const auto& tuple = headers_.http_headers(i);
      visitor(tuple.key(), tuple.value());
    }
  }
};

class DistributedHTTPHeadersWriter : public datadog::tracing::DictWriter {
  DistributedHTTPHeaders* headers_;

public:
  explicit DistributedHTTPHeadersWriter(DistributedHTTPHeaders* headers) : headers_(headers) {}

  void set(std::string_view key, std::string_view value) override {
    auto tuple = headers_->add_http_headers();
    tuple->set_key(std::string(key));
    tuple->set_value(std::string(value));
  }
};

struct ManualScheduler : public datadog::tracing::EventScheduler {
  std::function<void()> callback;

  Cancel schedule_recurring_event(std::chrono::steady_clock::duration /* interval */, std::function<void()> callback) override {
    assert(callback != nullptr);
    callback = callback;
    return []() {};
  }

  nlohmann::json config_json() const override { return nlohmann::json::object({{"type", "ManuaalScheduler"}}); }
};

class TracingService final : public APMClient::Service {
public:
  TracingService(std::unique_ptr<datadog::tracing::Tracer> tracer, std::shared_ptr<ManualScheduler> event_scheduler);
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
  std::unique_ptr<datadog::tracing::Tracer> tracer_;
  std::shared_ptr<ManualScheduler> event_scheduler_;
  std::unordered_map<int, datadog::tracing::Span> active_spans_;
};

TracingService::TracingService(std::unique_ptr<datadog::tracing::Tracer> tracer, std::shared_ptr<ManualScheduler> event_scheduler)
    : tracer_(std::move(tracer)), event_scheduler_(event_scheduler) {}

TracingService::~TracingService() {}

::grpc::Status TracingService::StartSpan(::grpc::ServerContext* /* context */, const ::StartSpanArgs* request, ::StartSpanReturn* response) {
  std::cout << "StartSpan" << std::endl;
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
    std::cerr << "unable to set origin." << std::endl;
  }

  auto span = tracer_->extract_or_create_span(DistributedHTTPHeadersReader(request->http_headers()), config);
  if (!span) {
    std::cerr << "could not extract span from http_headers" << std::endl;
    return ::grpc::Status(::grpc::StatusCode::INTERNAL, "could not extract span from http_headers");
  }

  active_spans_.insert({span->id(), std::move(*span)});
  response->set_trace_id(span->trace_id().low);
  response->set_span_id(span->id());
  std::cout << "StartSpan returning ok with trace_id " << response->trace_id() << " span_id " << response->span_id() << std::endl;
  return ::grpc::Status(::grpc::StatusCode::OK, "");
}

::grpc::Status TracingService::FinishSpan(::grpc::ServerContext* /* context */, const ::FinishSpanArgs* request, ::FinishSpanReturn* response) {
  (void)request;
  (void)response;
  std::cout << "FinishSpan" << std::endl;

  auto span_id = request->id();
  auto found = active_spans_.find(span_id);
  if (found == active_spans_.end()) {
    std::cout << "span not found for id " << span_id << std::endl;
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
    std::cout << "span not found for id " << span_id << std::endl;
    return ::grpc::Status(::grpc::StatusCode::INTERNAL, std::string() + "no active span for id " + std::to_string(span_id));
  }
  auto& span = found->second;
  span.set_tag(request->key(), request->value());

  return ::grpc::Status(::grpc::StatusCode::OK, "");
}

::grpc::Status TracingService::SpanSetMetric(::grpc::ServerContext* /* context */, const ::SpanSetMetricArgs* /* request */, ::SpanSetMetricReturn* /* response */) {
  return ::grpc::Status(::grpc::StatusCode::UNIMPLEMENTED, "");
}

::grpc::Status TracingService::SpanSetError(::grpc::ServerContext* /* context */, const ::SpanSetErrorArgs* request, ::SpanSetErrorReturn* /* response */) {
  auto span_id = request->span_id();
  auto found = active_spans_.find(span_id);
  if (found == active_spans_.end()) {
    std::cout << "span not found for id " << span_id << std::endl;
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

  return ::grpc::Status(::grpc::StatusCode::UNIMPLEMENTED, "");
}

::grpc::Status TracingService::InjectHeaders(::grpc::ServerContext* /* context */, const ::InjectHeadersArgs* request, ::InjectHeadersReturn* response) {
  std::cout << "InjectHeaders" << std::endl;
  (void)request;
  auto span_id = request->span_id();
  auto found = active_spans_.find(span_id);
  if (found == active_spans_.end()) {
    std::cout << "span not found for id " << span_id << std::endl;
    return ::grpc::Status(::grpc::StatusCode::INTERNAL, std::string() + "no active span for id " + std::to_string(span_id));
  }
  const auto& span = found->second;
  auto headers_writer = DistributedHTTPHeadersWriter(response->mutable_http_headers());
  span.inject(headers_writer);

  return ::grpc::Status(::grpc::StatusCode::OK, "");
}

::grpc::Status TracingService::FlushSpans(::grpc::ServerContext* /* context */, const ::FlushSpansArgs* request, ::FlushSpansReturn* response) {
  std::cout << "FlushSpans" << std::endl;
  (void)request;
  (void)response;
  event_scheduler_->callback();

  return ::grpc::Status(::grpc::StatusCode::OK, "");
}

::grpc::Status TracingService::FlushTraceStats(::grpc::ServerContext* /* context */, const ::FlushTraceStatsArgs* request, ::FlushTraceStatsReturn* response) {
  std::cout << "FlushTraceStats" << std::endl;
  (void)request;
  (void)response;
  return ::grpc::Status(::grpc::StatusCode::OK, "");
}

::grpc::Status TracingService::StopTracer(::grpc::ServerContext* /* context */, const ::StopTracerArgs* request, ::StopTracerReturn* response) {
  std::cout << "StopTracer" << std::endl;
  (void)request;
  (void)response;
  return ::grpc::Status(::grpc::StatusCode::UNIMPLEMENTED, "");
}

int main() {
  // get grpc port from environment variable
  // TODO: add some error checking
  int grpc_port = std::stoi(std::getenv("APM_TEST_CLIENT_SERVER_PORT"));

  auto event_scheduler = std::make_shared<ManualScheduler>();

  datadog::tracing::TracerConfig config;
  config.defaults.service = "cpp-parametric-test";
  config.defaults.environment = "staging";
  config.defaults.name = "grpc.request";
  config.agent.event_scheduler = event_scheduler;

  auto finalized_config = datadog::tracing::finalize_config(config);
  if (!finalized_config) {
    std::cerr << "error initializing dd-trace-cpp: " << finalized_config.error() << std::endl;
    return 1;
  }

  TracingService tracing_service(std::make_unique<datadog::tracing::Tracer>(*finalized_config), event_scheduler);

  grpc::ServerBuilder builder;
  builder.AddListeningPort("0.0.0.0:" + std::to_string(grpc_port), grpc::InsecureServerCredentials());
  builder.RegisterService(&tracing_service);

  std::unique_ptr<grpc::Server> server(builder.BuildAndStart());
  server->Wait();
  return 0;
}
