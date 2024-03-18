#include <datadog/cerr_logger.h>
#include <datadog/tracer.h>
#include <datadog/tracer_config.h>

#include <grpc/grpc.h>
#include <grpcpp/server_builder.h>

#include <cstdlib>

#include "developer_noise.h"
#include "scheduler.h"
#include "tracing_service.h"

int main() {
  // Initialize a logger that handles errors from the library as well as comforting developer-noise
  // from the tracing service.
  auto logger = std::make_shared<DeveloperNoiseLogger>();

  // Enable developer noise when a specific environment variable is set.
  auto verbose_env = std::getenv("CPP_PARAMETRIC_TEST_VERBOSE");
  if (verbose_env) {
    try {
      if (std::stoi(verbose_env) == 1) {
        logger->developer_noise(true);
      }
    } catch (...) {
    }
  }

  // An event scheduler needs to be shared between the TracingService and the tracer.
  auto event_scheduler = std::make_shared<ManualScheduler>();

  // Populate tracer configuration with our objects and values.
  datadog::tracing::TracerConfig config;
  config.logger = logger;
  config.agent.event_scheduler = event_scheduler;
  config.service = "cpp-parametric-test";
  config.environment = "staging";
  config.name = "grpc.request";

  // Finalize configuration so we can create a tracer.
  auto finalized_config = datadog::tracing::finalize_config(config);
  if (!finalized_config) {
    logger->log_error("unable to initialize tracer:");
    logger->log_error(finalized_config.error());
    return 1;
  }

  auto tracer = std::make_unique<datadog::tracing::Tracer>(*finalized_config);

  TracingService tracing_service(logger, std::move(tracer), event_scheduler);

  // TODO: check if the port is valid and all.
  auto grpc_port_env = std::getenv("APM_TEST_CLIENT_SERVER_PORT");
  if (grpc_port_env == nullptr) {
    logger->log_error("environment variable APM_TEST_CLIENT_SERVER_PORT is not set");
    return 1;
  }
  std::string grpc_port_str(grpc_port_env);

  // Initialize GRPC service with the provided port number
  grpc::ServerBuilder builder;
  builder.AddListeningPort("0.0.0.0:" + grpc_port_str, grpc::InsecureServerCredentials());
  builder.RegisterService(&tracing_service);

  // Launch things and block until finished.
  std::unique_ptr<grpc::Server> server(builder.BuildAndStart());
  server->Wait();
  return 0;
}
