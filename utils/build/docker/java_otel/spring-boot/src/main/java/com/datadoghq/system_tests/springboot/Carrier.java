package com.datadoghq.system_tests.springboot;

import datadog.trace.api.experimental.*;
import java.util.Map;
import java.util.Map.Entry;
import java.util.Set;

public class Carrier implements DataStreamsContextCarrier {
	public Map<String, Object> headers;
	
	public Carrier(Map<String, Object> headers) {
		this.headers = headers;
	}

	public Set<Entry<String, Object>> entries() {
		return this.headers.entrySet();
	}

	public void set(String key, String value){
		this.headers.put(key, value);
	}
}
