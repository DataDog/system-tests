#include "developer_noise.h"
#include "httplib.h"
#include "json.hpp"
#include "request_handler.h"

#include <datadog/optional.h>
#include <datadog/span_config.h>
#include <datadog/tracer.h>
#include <datadog/tracer_config.h>

#include <chrono>
#include <iostream>
#include <optional>
#include <string_view>
#include <unordered_map>

// `hard_stop` is installed as a signal handler for `SIGTERM`.
// For some reason, the default handler was not being called.
void hard_stop(int /*signal*/) { std::exit(0); }

std::optional<uint16_t> get_port() {
  try {
    auto port_env = std::getenv("APM_TEST_CLIENT_SERVER_PORT");
    if (port_env == nullptr) {
      return std::nullopt;
    }

    uint16_t port = std::atoi(port_env);
    return port;
  } catch (...) {
    return std::nullopt;
  }
}

int main() {
  auto logger = make_logger();

  auto port = get_port();
  if (!port) {
    logger->log_error("environment variable APM_TEST_CLIENT_SERVER_PORT is not set or the port is not valid");
    return 1;
  }

  // An event scheduler needs to be shared between the TracingService and the tracer.
  auto event_scheduler = std::make_shared<ManualScheduler>();

  datadog::tracing::TracerConfig config;
  config.logger = logger;
  config.agent.event_scheduler = event_scheduler;
  config.service = "cpp-parametric-test";
  config.environment = "staging";
  config.name = "http.request";

  auto finalized_config = datadog::tracing::finalize_config(config);
  if (auto error = finalized_config.if_error()) {
    logger->log_error(error->with_prefix("unable to initialize tracer:"));
    return 1;
  }

  RequestHandler handler(*finalized_config, event_scheduler, logger);

  httplib::Server svr;
  svr.Post("/trace/span/start", [&handler](const httplib::Request& req, httplib::Response& res) { handler.on_span_start(req, res); });
  svr.Post("/trace/span/finish", [&handler](const httplib::Request& req, httplib::Response& res) { handler.on_span_end(req, res); });
  svr.Post("/trace/span/set_meta", [&handler](const httplib::Request& req, httplib::Response& res) { handler.on_set_meta(req, res); });
  svr.Post("/trace/span/inject_headers", [&handler](const httplib::Request& req, httplib::Response& res) { handler.on_inject_headers(req, res); });
  svr.Post("/trace/span/flush", [&handler](const httplib::Request& req, httplib::Response& res) { handler.on_span_flush(req, res); });
  svr.Post("/trace/stats/flush", [&handler](const httplib::Request& req, httplib::Response& res) { handler.on_stats_flush(req, res); });

  // Not implemented
  svr.Post("/trace/span/set_metric", [&handler](const httplib::Request& req, httplib::Response& res) { handler.on_set_metric(req, res); });

  svr.set_logger([&logger](const auto& req, const auto&) {
    std::string msg{req.method};
    msg += " ";
    msg += req.path;
    msg += " ";
    msg += req.version;
    logger->log_info(msg);

    if (!req.body.empty()) {
      msg = "   body: ";
      msg += req.body;
      logger->log_info(msg);
    }
  });

  svr.set_exception_handler([](const auto&, auto& res, std::exception_ptr ep) {
    try {
      std::rethrow_exception(ep);
    } catch (const nlohmann::json::exception& e) {
      // clang-format off
      nlohmann::json j{
        {"detail", {
          {"loc", nlohmann::json::array({__FILE__, __LINE__})},
          {"type", "JSON Parsing error"},
          {"msg", e.what()}
        }}
      };
      // clang-format on

      res.set_content(j.dump(), "application/json");
      res.status = 422;
      return;
    } catch (std::exception& e) {
      res.set_content(e.what(), "text/plain");
    } catch (...) {
      res.set_content("Unknown Exception", "text/plain");
    }

    res.status = 500;
  });

  std::signal(SIGTERM, hard_stop);
  svr.listen("0.0.0.0", *port);
  return 0;
}
