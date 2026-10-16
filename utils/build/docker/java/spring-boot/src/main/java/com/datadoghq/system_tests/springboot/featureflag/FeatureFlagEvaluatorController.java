package com.datadoghq.system_tests.springboot.featureflag;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

import datadog.trace.api.openfeature.Provider;
import dev.openfeature.sdk.Client;
import dev.openfeature.sdk.EvaluationContext;
import dev.openfeature.sdk.FeatureProvider;
import dev.openfeature.sdk.FlagEvaluationDetails;
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
import org.springframework.web.bind.annotation.RestController;

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
        final Map<String, Object> result = new HashMap<>();
        final List<String> targetingKeys = request.getTargetingKeys() == null || request.getTargetingKeys().isEmpty()
                ? List.of(request.getTargetingKey())
                : request.getTargetingKeys();
        try {
            for (final String targetingKey : targetingKeys) {
                result.clear();
                final EvaluationContext context = context(request, targetingKey);
                final FlagEvaluationDetails<?> details;
                switch (request.getVariationType()) {
                    case "BOOLEAN":
                        details = client.getBooleanDetails(request.getFlag(), (Boolean) request.getDefaultValue(), context);
                        break;
                    case "STRING":
                        details = client.getStringDetails(request.getFlag(), (String) request.getDefaultValue(), context);
                        break;
                    case "INTEGER":
                        details = client.getIntegerDetails(request.getFlag(), (Integer) request.getDefaultValue(), context);
                        break;
                    case "NUMERIC":
                        final Number number = (Number) request.getDefaultValue();
                        if (number instanceof Double) {
                            details = client.getDoubleDetails(request.getFlag(), number.doubleValue(), context);
                        } else {
                            details = client.getIntegerDetails(request.getFlag(), number.intValue(), context);
                        }
                        break;
                    case "JSON":
                        details = client.getObjectDetails(request.getFlag(), Value.objectToValue(request.getDefaultValue()), context);
                        break;
                    default:
                        throw new IllegalArgumentException("Unsupported variation type: " + request.getVariationType());
                }
                final Object value = details.getValue();
                result.put("value", value instanceof Value ? context.convertValue((Value) value) : value);
                result.put("reason", details.getReason());
                result.put("variant", details.getVariant());
                result.put("errorCode", details.getErrorCode());
                result.put("errorMessage", details.getErrorMessage());
                if (details.getFlagMetadata() != null) {
                    result.put("allocationKey", details.getFlagMetadata().getString("allocationKey"));
                    result.put("serialId", details.getFlagMetadata().getInteger("__dd_split_serial_id"));
                    result.put("flagMetadata", details.getFlagMetadata().asUnmodifiableMap());
                }
            }
        } catch (Throwable e) {
            LOGGER.error("Error on resolution", e);
            result.clear();
            result.put("value", request.getDefaultValue());
            result.put("reason", "ERROR");
            result.put("errorMessage", e.getMessage());
        }
        result.put("count", targetingKeys.size());
        return ResponseEntity.ok(result);
    }

    private static EvaluationContext context(final EvaluateRequest request, final String targetingKey) {
        final MutableContext context = new MutableContext();
        context.setTargetingKey(targetingKey);
        request.attributes.forEach((key, value) -> {
            if (value instanceof Boolean) {
                context.add(key, (Boolean) value);
            } else if (value instanceof Integer) {
                context.add(key, (Integer) value);
            } else if (value instanceof Long) {
                // OpenFeature represents numbers outside the Integer range as Double.
                context.add(key, ((Long) value).doubleValue());
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
