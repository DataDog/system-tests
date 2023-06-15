#pragma once

#include <datadog/event_scheduler.h>
#include <datadog/json.hpp>

struct ManualScheduler : public datadog::tracing::EventScheduler {
  std::function<void()> manual_flush;

  Cancel schedule_recurring_event(std::chrono::steady_clock::duration /* interval */, std::function<void()> callback) override {
    assert(callback != nullptr);
    manual_flush = callback;
    return []() {};
  }

  nlohmann::json config_json() const override { return nlohmann::json::object({{"type", "ManuaalScheduler"}}); }
};
