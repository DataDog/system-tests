#include "developer_noise.h"

#include <iostream>

void DeveloperNoiseLogger::developer_noise(bool enabled) { developer_noise_ = enabled; }

void DeveloperNoiseLogger::log_info(datadog::tracing::StringView message) {
  if (developer_noise_) {
    make_noise([&](auto& stream) { stream << message; });
  }
}

void DeveloperNoiseLogger::log_error(const LogFunc& insert_to_stream) { make_noise(insert_to_stream); }

void DeveloperNoiseLogger::log_startup(const LogFunc& insert_to_stream) { make_noise(insert_to_stream); }

void DeveloperNoiseLogger::make_noise(const LogFunc& insert_to_stream) {
  std::lock_guard<std::mutex> lock(mutex_);
  insert_to_stream(std::cerr);
  std::cerr << std::endl;
}
