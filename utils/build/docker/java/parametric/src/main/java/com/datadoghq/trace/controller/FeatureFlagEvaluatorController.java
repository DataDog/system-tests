package com.datadoghq.trace.controller;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

import com.fasterxml.jackson.annotation.JsonAlias;
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
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

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
            final boolean featureFlaggingConfigured =
                    System.getenv("DD_FEATURE_FLAGS_ENABLED") != null
                            || System.getenv("DD_FEATURE_FLAGS_CONFIGURATION_SOURCE") != null
                            || System.getenv("DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_BASE_URL") != null
                            || Boolean.parseBoolean(System.getenv("DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED"));
            final FeatureProvider provider;
            if (featureFlaggingConfigured) {
                provider = new Provider(new Provider.Options().initTimeout(100, TimeUnit.MILLISECONDS));
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
    public synchronized ResponseEntity<Boolean> start(@RequestBody(required = false) final Map<String, Object> request) {
        if (request != null && request.containsKey("providerOptions")) {
            final Object requestedOptions = request.get("providerOptions");
            if (!(requestedOptions instanceof Map<?, ?> optionsMap)) {
                return ResponseEntity.badRequest().body(false);
            }
            final Provider.Options options = new Provider.Options().initTimeout(100, TimeUnit.MILLISECONDS);
            try {
                for (Map.Entry<?, ?> entry : optionsMap.entrySet()) {
                    final String name = String.valueOf(entry.getKey());
                    if ((!name.equals("enableExperimentationOptOutParameter")
                            && !name.equals("enableEvaluationTelemetryOptOutParameter"))
                            || !(entry.getValue() instanceof Boolean)) {
                        return ResponseEntity.badRequest().body(false);
                    }
                    // A missing public API is a start failure, not a behavioral negative control.
                    Provider.Options.class.getMethod(name, boolean.class).invoke(options, entry.getValue());
                }
                // Resolve the lazy default provider before replacing it with explicit options.
                client.getProviderState();
                OpenFeatureAPI.getInstance().setProviderAndWait(new Provider(options));
            } catch (ReflectiveOperationException error) {
                LOGGER.error("Requested provider option is unavailable", error);
                return ResponseEntity.internalServerError().body(false);
            }
        }
        final ProviderState state = client.getProviderState();
        if (state == ProviderState.READY) {
            return ResponseEntity.ok(true);
        } else {
            return ResponseEntity.internalServerError().body(false);
        }
    }

    @PostMapping(value = "/evaluate", consumes = APPLICATION_JSON_VALUE, produces = APPLICATION_JSON_VALUE)
    public ResponseEntity<Map<String, Object>> evaluate(@RequestBody final EvaluateRequest request) {
        final Map<String, Object> result = new HashMap<>();
        final EvaluationContext context = context(request);
        try {
            final FlagEvaluationDetails<?> details = switch (request.getVariationType()) {
                case "BOOLEAN" ->
                        client.getBooleanDetails(request.getFlag(), (Boolean) request.getDefaultValue(), context);
                case "STRING" -> client.getStringDetails(request.getFlag(), (String) request.getDefaultValue(), context);
                case "INTEGER" -> {
                    final Number integerEval = (Number) request.getDefaultValue();
                    yield client.getIntegerDetails(request.getFlag(), integerEval.intValue(), context);
                }
                case "NUMERIC" -> {
                    final Number doubleEval = (Number) request.getDefaultValue();
                    yield client.getDoubleDetails(request.getFlag(), doubleEval.doubleValue(), context);
                }
                case "JSON" -> client.getObjectDetails(request.getFlag(), Value.objectToValue(request.getDefaultValue()), context);
                default -> throw new IllegalArgumentException("Unsupported variation type: " + request.getVariationType());
            };
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
        } catch (Throwable e) {
            LOGGER.error("Error on resolution", e);
            result.clear();
            result.put("value", request.getDefaultValue());
            result.put("reason", "ERROR");
            result.put("errorMessage", e.getMessage());
        }
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
