package com.datadoghq.system_tests.springboot.data_streams;

import com.fasterxml.jackson.annotation.JsonProperty;
import datadog.trace.api.experimental.DataStreamsContextCarrier;
import java.util.Map;
import java.util.Map.Entry;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

public class DSMContextCarrier implements DataStreamsContextCarrier {
    @JsonProperty
    private Map<String, Object> data;

    public DSMContextCarrier() {
      this.data = new ConcurrentHashMap<>();
    }

    public DSMContextCarrier(Map<String, Object> data) {
      this.data = data;
    }

    @Override
    public synchronized Set<Map.Entry<String, Object>> entries() {
      return data.entrySet();
    }

    @Override
    public synchronized void set(String key, String value) {
      data.put(key, value);
    }

    public synchronized Map<String, Object> getData() {
      return data;
    }
}
