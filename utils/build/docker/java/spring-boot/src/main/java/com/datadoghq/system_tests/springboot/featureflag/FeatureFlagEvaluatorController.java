package com.datadoghq.system_tests.springboot.featureflag;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

import datadog.trace.api.openfeature.Provider;
import dev.openfeature.sdk.Client;
import dev.openfeature.sdk.EvaluationContext;
import dev.openfeature.sdk.FeatureProvider;
import dev.openfeature.sdk.FlagEvaluationDetails;
import dev.openfeature.sdk.MutableContext;
import dev.openfeature.sdk.MutableStructure;
import dev.openfeature.sdk.NoOpProvider;
import dev.openfeature.sdk.OpenFeatureAPI;
import dev.openfeature.sdk.ProviderState;
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
import org.springframework.web.bind.annotation.RestController;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
public class FeatureFlagEvaluatorController {

    @Configuration
    public static class FeatureFlagEvaluatorConfig {

        @Lazy
        @Bean
        public Client client() {
            final OpenFeatureAPI api = OpenFeatureAPI.getInstance();
            final boolean featureFlaggingConfigured =
                    System.getenv("DD_FEATURE_FLAGS_ENABLED") != null
                            || System.getenv("DD_FEATURE_FLAGS_CONFIGURATION_SOURCE") != null
                            || System.getenv("DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_BASE_URL") != null
                            || Boolean.parseBoolean(System.getenv("DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED"));
            final FeatureProvider provider;
            if (featureFlaggingConfigured) {
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

    private static final Logger LOGGER = LoggerFactory.getLogger(FeatureFlagEvaluatorController.class);

    @Autowired
    @Lazy
    private Client client;

    @PostMapping(value = "/ffe", consumes = APPLICATION_JSON_VALUE, produces = APPLICATION_JSON_VALUE)
    public ResponseEntity<Map<String, Object>> evaluate(@RequestBody final EvaluateRequest request) {
        Object value;
        FlagEvaluationDetails<?> details = null;
        String reason = "DEFAULT";
        String errorMessage = null;
        final List<String> targetingKeys = request.getTargetingKeys() == null || request.getTargetingKeys().isEmpty()
                ? Collections.singletonList(request.getTargetingKey())
                : request.getTargetingKeys();
        try {
            value = request.getDefaultValue();
            for (final String targetingKey : targetingKeys) {
                final EvaluationContext context = context(request, targetingKey);
                switch (request.getVariationType()) {
                    case "BOOLEAN":
                        details = client.getBooleanDetails(request.getFlag(), (Boolean) request.getDefaultValue(), context);
                        break;
                    case "STRING":
                        details = client.getStringDetails(request.getFlag(), (String) request.getDefaultValue(), context);
                        break;
                    case "INTEGER":
                        details = client.getIntegerDetails(request.getFlag(), ((Number) request.getDefaultValue()).intValue(), context);
                        break;
                    case "NUMERIC":
                        details = client.getDoubleDetails(request.getFlag(), ((Number) request.getDefaultValue()).doubleValue(), context);
                        break;
                    case "JSON":
                        details = client.getObjectDetails(request.getFlag(), valueOf(request.getDefaultValue()), context);
                        break;
                    default:
                        details = null;
                }
                if (details != null) {
                    value = details.getValue() instanceof Value
                            ? context.convertValue((Value) details.getValue())
                            : details.getValue();
                    reason = details.getReason();
                    errorMessage = details.getErrorMessage();
                }
            }
        } catch (Throwable e) {
            LOGGER.error("Error on resolution", e);
            details = null;
            value = request.getDefaultValue();
            reason = "ERROR";
            errorMessage = e.getMessage();
        }
        final Map<String, Object> flagMetadata = details == null || details.getFlagMetadata() == null
                ? Collections.emptyMap() : details.getFlagMetadata().asUnmodifiableMap();
        final Map<String, Object> result = new HashMap<>();
        result.put("reason", reason);
        result.put("value", value);
        result.put("count", targetingKeys.size());
        result.put("errorCode", details == null || details.getErrorCode() == null ? null : details.getErrorCode().name());
        result.put("errorMessage", errorMessage);
        result.put("variant", details == null ? null : details.getVariant());
        result.put("flagMetadata", flagMetadata);
        if (flagMetadata.containsKey("allocationKey")) {
            result.put("allocationKey", flagMetadata.get("allocationKey"));
        }
        return ResponseEntity.ok(result);
    }

    private static EvaluationContext context(final EvaluateRequest request, final String targetingKey) {
        final Map<String, Value> attributes = new HashMap<>();
        if (request.getAttributes() != null) {
            request.getAttributes().forEach((key, value) -> attributes.put(key, valueOf(value)));
        }
        return new MutableContext(targetingKey, attributes);
    }

    private static Value valueOf(final Object value) {
        if (value instanceof Long) {
            // OpenFeature 1.18.2 represents numbers as Integer or Double.
            return new Value(((Long) value).doubleValue());
        }
        if (value instanceof Map) {
            final Map<String, Value> fields = new HashMap<>();
            ((Map<?, ?>) value).forEach((key, field) -> fields.put((String) key, valueOf(field)));
            return new Value(new MutableStructure(fields));
        }
        if (value instanceof List) {
            final List<Value> values = new ArrayList<>();
            ((List<?>) value).forEach(item -> values.add(valueOf(item)));
            return new Value(values);
        }
        return Value.objectToValue(value);
    }

    public static class EvaluateRequest {
        private String flag;
        private String variationType;
        private Object defaultValue;
        private String targetingKey;
        private List<String> targetingKeys;
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

        public List<String> getTargetingKeys() {
            return targetingKeys;
        }

        public void setTargetingKeys(List<String> targetingKeys) {
            this.targetingKeys = targetingKeys;
        }

        public String getVariationType() {
            return variationType;
        }

        public void setVariationType(String variationType) {
            this.variationType = variationType;
        }
    }
}
