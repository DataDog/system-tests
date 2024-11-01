#include <datadog/cerr_logger.h>
#include <datadog/tracer.h>
#include <datadog/tracer_config.h>

#include <pistache/endpoint.h>
#include <pistache/http.h>
#include <pistache/router.h>

#include <cstdlib>

#include "developer_noise.h"
#include "scheduler.h"
#include "tracing_service.h"

// Define a Pistache HTTP server class
class HttpServer {
public:
    HttpServer(const std::shared_ptr<DeveloperNoiseLogger>& logger,
               std::unique_ptr<datadog::tracing::Tracer> tracer,
               std::shared_ptr<ManualScheduler> event_scheduler)
        : logger(logger), tracer(std::move(tracer)), event_scheduler(event_scheduler) {
        router.post("/trace", Pistache::Router::bind(&HttpServer::handleTrace, this));
    }

    void init(size_t port) {
        auto opts = Pistache::Http::Endpoint::options().threads(1);
        httpEndpoint.init(Pistache::Address(Pistache::Ipv4::any(), Pistache::Port(port)), opts);
    }

    void start() {
        httpEndpoint.setHandler(router.handler());
        httpEndpoint.serve();
    }

private:
    void handleTrace(const Pistache::Rest::Request& request, Pistache::Http::ResponseWriter response) {
        // Handle the tracing logic using the Tracer and log appropriately
        // Implementation depends on how you want to handle traces
        response.send(Pistache::Http::Code::Ok, "Tracing initiated");
    }

    Pistache::Http::Endpoint httpEndpoint;
    Pistache::Rest::Router router;
    std::shared_ptr<DeveloperNoiseLogger> logger;
    std::unique_ptr<datadog::tracing::Tracer> tracer;
    std::shared_ptr<ManualScheduler> event_scheduler;
};

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

    // An event scheduler needs to be shared between the HttpServer and the tracer.
    auto event_scheduler = std::make_shared<ManualScheduler>();

    // Populate tracer configuration with our objects and values.
    datadog::tracing::TracerConfig config;
    config.logger = logger;
    config.agent.event_scheduler = event_scheduler;
    config.service = "cpp-parametric-test";
    config.environment = "staging";
    config.name = "http.request";

    // Finalize configuration so we can create a tracer.
    auto finalized_config = datadog::tracing::finalize_config(config);
    if (!finalized_config) {
        logger->log_error("unable to initialize tracer:");
        logger->log_error(finalized_config.error());
        return 1;
    }

    auto tracer = std::make_unique<datadog::tracing::Tracer>(*finalized_config);

    HttpServer http_server(logger, std::move(tracer), event_scheduler);

    // TODO: check if the port is valid and all.
    auto http_port_env = std::getenv("APM_TEST_CLIENT_SERVER_PORT");
    if (http_port_env == nullptr) {
        logger->log_error("environment variable APM_TEST_CLIENT_SERVER_PORT is not set");
        return 1;
    }
    size_t port = std::stoi(http_port_env);

    // Initialize and start the Pistache HTTP server
    http_server.init(port);
    http_server.start();

    return 0;
}
