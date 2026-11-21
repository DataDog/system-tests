package com.datadoghq.system_tests.springboot.featureflag;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

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

    // One client per combination of provider options, each in its own OpenFeature domain.
    private final Map<String, Client> optionClients = new HashMap<>();

    @PostMapping(value = "/ffe", consumes = APPLICATION_JSON_VALUE, produces = APPLICATION_JSON_VALUE)
    public ResponseEntity<Map<String, Object>> evaluate(@RequestBody final EvaluateRequest request) {
        return ResponseEntity.ok(evaluate(client, request));
    }

    /**
     * Evaluates like /ffe, through the client of an OpenFeature domain whose Datadog provider is built with the
     * requested evaluationTelemetryEnabled and exposuresEnabled options. The options are looked up by reflection so
     * the weblog still builds against SDK versions without them; those versions answer 501.
     */
    @PostMapping(value = "/ffe/provider-options", consumes = APPLICATION_JSON_VALUE, produces = APPLICATION_JSON_VALUE)
    public ResponseEntity<Map<String, Object>> evaluateWithProviderOptions(@RequestBody final EvaluateRequest request) {
        final boolean evaluationTelemetry = !Boolean.FALSE.equals(request.getEvaluationTelemetryEnabled());
        final boolean exposures = !Boolean.FALSE.equals(request.getExposuresEnabled());
        final Client optionClient;
        try {
            optionClient = optionClient(evaluationTelemetry, exposures);
        } catch (final NoSuchMethodException e) {
            final Map<String, Object> result = new HashMap<>();
            result.put("errorCode", "UNSUPPORTED");
            result.put("errorMessage", "Provider.Options does not support " + e.getMessage());
            return ResponseEntity.status(501).body(result);
        } catch (final Exception e) {
            LOGGER.error("Error creating the provider", e);
            final Map<String, Object> result = new HashMap<>();
            result.put("errorCode", "GENERAL");
            result.put("errorMessage", String.valueOf(e));
            return ResponseEntity.status(500).body(result);
        }
        return ResponseEntity.ok(evaluate(optionClient, request));
    }

    private synchronized Client optionClient(final boolean evaluationTelemetry, final boolean exposures)
            throws Exception {
        final String domain = "telemetry-" + evaluationTelemetry + "-exposures-" + exposures;
        Client optionClient = optionClients.get(domain);
        if (optionClient == null) {
            final Provider.Options options = new Provider.Options();
            options.getClass().getMethod("evaluationTelemetryEnabled", boolean.class).invoke(options, evaluationTelemetry);
            options.getClass().getMethod("exposuresEnabled", boolean.class).invoke(options, exposures);
            final OpenFeatureAPI api = OpenFeatureAPI.getInstance();
            api.setProviderAndWait(domain, new Provider(options));
            optionClient = api.getClient(domain);
            optionClients.put(domain, optionClient);
        }
        return optionClient;
    }

    private static Map<String, Object> evaluate(final Client client, final EvaluateRequest request) {
        Object value;
        String reason;
        final List<String> targetingKeys = request.getTargetingKeys() == null || request.getTargetingKeys().isEmpty()
                ? List.of(request.getTargetingKey())
                : request.getTargetingKeys();
        try {
            value = request.getDefaultValue();
            for (final String targetingKey : targetingKeys) {
                final EvaluationContext context = context(request, targetingKey);
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
        result.put("count", targetingKeys.size());
        return result;
    }

    private static EvaluationContext context(final EvaluateRequest request, final String targetingKey) {
        final MutableContext context = new MutableContext();
        context.setTargetingKey(targetingKey);
        request.attributes.forEach((key, value) -> {
            if (value instanceof Boolean) {
                context.add(key, (Boolean) value);
            } else if (value instanceof Integer) {
                context.add(key, (Integer) value);
            } else if (value instanceof Number) {
                // Jackson uses Long for JSON integers outside the Integer range.
                context.add(key, ((Number) value).doubleValue());
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
        private Boolean evaluationTelemetryEnabled;
        private Boolean exposuresEnabled;

        public Boolean getEvaluationTelemetryEnabled() {
            return evaluationTelemetryEnabled;
        }

        public void setEvaluationTelemetryEnabled(Boolean evaluationTelemetryEnabled) {
            this.evaluationTelemetryEnabled = evaluationTelemetryEnabled;
        }

        public Boolean getExposuresEnabled() {
            return exposuresEnabled;
        }

        public void setExposuresEnabled(Boolean exposuresEnabled) {
            this.exposuresEnabled = exposuresEnabled;
        }

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
