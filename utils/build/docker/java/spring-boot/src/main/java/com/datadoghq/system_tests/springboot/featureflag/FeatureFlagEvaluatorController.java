package com.datadoghq.system_tests.springboot.featureflag;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

import datadog.trace.api.openfeature.Provider;
import dev.openfeature.sdk.Client;
import dev.openfeature.sdk.EvaluationContext;
import dev.openfeature.sdk.MutableContext;
import dev.openfeature.sdk.OpenFeatureAPI;
import dev.openfeature.sdk.Structure;
import dev.openfeature.sdk.Value;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
public class FeatureFlagEvaluatorController {

    private static final Logger LOGGER = LoggerFactory.getLogger(FeatureFlagEvaluatorController.class);

    private final Client client;

    public FeatureFlagEvaluatorController() {
        final OpenFeatureAPI api = OpenFeatureAPI.getInstance();
        api.setProvider(new Provider());
        client = api.getClient();
    }

    @PostMapping(value = "/ffe", consumes = APPLICATION_JSON_VALUE, produces = APPLICATION_JSON_VALUE)
    public ResponseEntity<Map<String, Object>> evaluate(@RequestBody final EvaluateRequest request) {
        Object value;
        String reason;
        final EvaluationContext context = context(request);
        try {
            switch (request.getVariationType()) {
                case "BOOLEAN":
                    value = client.getBooleanValue(request.getFlag(), (Boolean) request.getDefaultValue(), context);
                    break;
                case "STRING":
                    value = client.getStringValue(request.getFlag(), (String) request.getDefaultValue(), context);
                    break;
                case "INTEGER":
                    value = client.getIntegerValue(request.getFlag(), (Integer) request.getDefaultValue(), context);
                    break;
                case "NUMERIC":
                    final Number number = (Number) request.getDefaultValue();
                    if (number instanceof Double) {
                        value = client.getDoubleValue(request.getFlag(), number.doubleValue(), context);
                    } else {
                        value = client.getIntegerValue(request.getFlag(), number.intValue(), context);
                    }
                    break;
                case "JSON":
                    final Value objectValue = client.getObjectValue(request.getFlag(), Value.objectToValue(request.getDefaultValue()), context);
                    value = context.convertValue(objectValue);
                    break;
                default:
                    value = request.getDefaultValue();
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
        private String variationType;
        private Object defaultValue;
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
