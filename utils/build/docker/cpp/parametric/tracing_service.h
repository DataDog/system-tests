#pragma once

#include <pistache/http.h>
#include <pistache/endpoint.h>
#include <datadog/cerr_logger.h>
#include <datadog/span.h>
#include <datadog/tracer.h>
#include "developer_noise.h"
#include "scheduler.h"

class TracingService : public Pistache::Http::Handler {
public:
  HTTP_PROTOTYPE(TracingService)

  TracingService(std::shared_ptr<DeveloperNoiseLogger> logger,
             std::unique_ptr<datadog::tracing::Tracer> tracer,
             std::shared_ptr<ManualScheduler> event_scheduler);

  virtual ~TracingService() = default;

  void onRequest(const Pistache::Http::Request& request,
             Pistache::Http::ResponseWriter response) override;

private:
  void handleStartSpan(const Pistache::Http::Request& request, 
                 Pistache::Http::ResponseWriter response);
  void handleFinishSpan(const Pistache::Http::Request& request, 
                  Pistache::Http::ResponseWriter response);
  void handleSpanSetMeta(const Pistache::Http::Request& request, 
                   Pistache::Http::ResponseWriter response);
  void handleSpanSetMetric(const Pistache::Http::Request& request, 
                   Pistache::Http::ResponseWriter response);
  void handleSpanSetError(const Pistache::Http::Request& request, 
                  Pistache::Http::ResponseWriter response);
  void handleInjectHeaders(const Pistach
