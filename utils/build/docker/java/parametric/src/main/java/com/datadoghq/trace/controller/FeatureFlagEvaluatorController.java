package com.datadoghq.trace.controller;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

import com.datadoghq.trace.opentracing.controller.OpenTracingController;
import com.fasterxml.jackson.annotation.JsonAlias;
import datadog.trace.api.DDSpanId;
import datadog.trace.api.openfeature.Provider;
import dev.openfeature.sdk.Client;
import dev.openfeature.sdk.EvaluationContext;
import dev.openfeature.sdk.FeatureProvider;
import dev.openfeature.sdk.MutableContext;
import dev.openfeature.sdk.NoOpProvider;
import dev.openfeature.sdk.OpenFeatureAPI;
import dev.openfeature.sdk.ProviderState;
import dev.openfeature.sdk.Structure;
import dev.openfeature.sdk.Value;
import io.opentracing.Scope;
import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Lazy;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/ffe")
public class FeatureFlagEvaluatorController {

    private static final Logger LOGGER = LoggerFactory.getLogger(FeatureFlagEvaluatorController.class);

    @Configuration
    public static class FeatureFlagEvaluatorConfig {

        @Lazy
        @Bean
        public Client client() {
            final OpenFeatureAPI api = OpenFeatureAPI.getInstance();
            final String envProperty = System.getenv("DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED");
            final FeatureProvider provider;
            if (Boolean.parseBoolean(envProperty)) {
                provider = new Provider();
            } else {
                provider = new NoOpProvider() {
                    @Override
                    public ProviderState getState() {
                        return ProviderState.READY;
                    }
                };
            }
            api.setProviderAndWait(provider);
            return api.getClient();
        }
    }

    @Autowired
    @Lazy
    private Client client;

    @PostMapping(value = "/start")
    public ResponseEntity<Boolean> start() {
        final ProviderState state = client.getProviderState();
        if (state == ProviderState.READY) {
            return ResponseEntity.ok(true);
        } else {
            return ResponseEntity.internalServerError().body(false);
        }
    }

    @PostMapping(value = "/evaluate", consumes = APPLICATION_JSON_VALUE, produces = APPLICATION_JSON_VALUE)
    public ResponseEntity<Map<String, Object>> evaluate(@RequestBody final EvaluateRequest request) {
        Object value;
        String reason;
        final EvaluationContext context = context(request);
        // Re-activate the caller-supplied root span around the eval so the ffe_* tags (Phase 2) land
        // on the test's span. The client sends span_id as a decimal STRING (see
        // _test_client_parametric.py:814-815); the OT registry is keyed by DDSpanId.from(...).
        // An unknown/missing/unparsable span_id leaves target null -> skip activation, never throw (T-01-DOS).
        final Span target = resolveSpan(request.getSpanId());
        try {
            if (target != null) {
                try (Scope scope = GlobalTracer.get().scopeManager().activate(target)) {
                    value = evaluate(request, context);
                }
            } else {
                value = evaluate(request, context);
            }
            reason = "DEFAULT";
        } catch (Throwable e) {
            LOGGER.error("Error on resolution", e);
            value = request.getDefaultValue();
            reason = "ERROR";
        }
        final Map<String, Object> result = new HashMap<>();
        result.put("reason", reason);
        result.put("value", value);
        return ResponseEntity.ok(result);
    }

    /** Look up a span by the (string) span_id the test client sends; null when missing/unparsable. */
    private static Span resolveSpan(final String spanId) {
        if (spanId == null || spanId.isEmpty()) {
            return null;
        }
        try {
            return OpenTracingController.getSpan(DDSpanId.from(spanId));
        } catch (Throwable e) {
            LOGGER.warn("Could not resolve span for span_id {}", spanId, e);
            return null;
        }
    }

    private Object evaluate(final EvaluateRequest request, final EvaluationContext context) {
        return switch (request.getVariationType()) {
            case "BOOLEAN" ->
                    client.getBooleanValue(request.getFlag(), (Boolean) request.getDefaultValue(), context);
            case "STRING" -> client.getStringValue(request.getFlag(), (String) request.getDefaultValue(), context);
            case "INTEGER" -> {
                final Number integerEval = (Number) request.getDefaultValue();
                yield client.getIntegerValue(request.getFlag(), integerEval.intValue(), context);
            }
            case "NUMERIC" -> {
                final Number doubleEval = (Number) request.getDefaultValue();
                yield client.getDoubleValue(request.getFlag(), doubleEval.doubleValue(), context);
            }
            case "JSON" -> {
                final Value objectValue = client.getObjectValue(request.getFlag(), Value.objectToValue(request.getDefaultValue()), context);
                yield context.convertValue(objectValue);
            }
            default -> request.getDefaultValue();
        };
    }

    private static EvaluationContext context(final EvaluateRequest request) {
        final MutableContext context = new MutableContext();
        context.setTargetingKey(request.getTargetingKey());
        request.attributes.forEach((key, value) -> {
            if (value instanceof Boolean) {
                context.add(key, (Boolean) value);
            } else if (value instanceof Integer) {
                context.add(key, (Integer) value);
            } else if (value instanceof Double) {
                context.add(key, (Double) value);
            } else if (value instanceof String) {
                context.add(key, (String) value);
            } else if (value instanceof Map) {
                context.add(key, Value.objectToValue(value).asStructure());
            } else if (value instanceof List) {
                context.add(key, Value.objectToValue(value).asList());
            } else {
                context.add(key, (Structure) null);
            }
        });
        return context;
    }

    public static class EvaluateRequest {
        private String flag;
        @JsonAlias("variation_type")
        private String variationType;
        @JsonAlias("default_value")
        private Object defaultValue;
        @JsonAlias("targeting_key")
        private String targetingKey;
        // The test client sends span_id as a STRING (see _test_client_parametric.py:814-815).
        @JsonAlias("span_id")
        private String spanId;
        private Map<String, Object> attributes;

        public Map<String, Object> getAttributes() {
            return attributes;
        }

        public String getSpanId() {
            return spanId;
        }

        public void setSpanId(String spanId) {
            this.spanId = spanId;
        }

        public void setAttributes(Map<String, Object> attributes) {
            this.attributes = attributes;
        }

        public Object getDefaultValue() {
            return defaultValue;
        }

        public void setDefaultValue(Object defaultValue) {
            this.defaultValue = defaultValue;
        }

        public String getFlag() {
            return flag;
        }

        public void setFlag(String flag) {
            this.flag = flag;
        }

        public String getTargetingKey() {
            return targetingKey;
        }

        public void setTargetingKey(String targetingKey) {
            this.targetingKey = targetingKey;
        }

        public String getVariationType() {
            return variationType;
        }

        public void setVariationType(String variationType) {
            this.variationType = variationType;
        }
    }
}
