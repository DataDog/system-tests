package com.datadoghq.trace.controller;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

import com.fasterxml.jackson.annotation.JsonAlias;
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
        try {
            value = switch (request.getVariationType()) {
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
        private Map<String, Object> attributes;

        public Map<String, Object> getAttributes() {
            return attributes;
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
