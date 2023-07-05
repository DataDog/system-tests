#pragma once

#include <algorithm>
#include <cctype>

#include <datadog/dict_reader.h>
#include <datadog/dict_writer.h>

#include "test_proto3_optional/apm_test_client.pb.h"

class DistributedHTTPHeadersReader : public datadog::tracing::DictReader {
  const DistributedHTTPHeaders& headers_;

public:
  DistributedHTTPHeadersReader(const DistributedHTTPHeaders& headers) : headers_(headers) {}

  datadog::tracing::Optional<datadog::tracing::StringView> lookup(datadog::tracing::StringView key) const override {
    for (int i = 0; i < headers_.http_headers_size(); i++) {
      std::string lookup_key(headers_.http_headers(i).key());
      std::transform(lookup_key.cbegin(), lookup_key.cend(), lookup_key.begin(), [](unsigned char c) { return std::tolower(c); });
      if (lookup_key == key) {
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
