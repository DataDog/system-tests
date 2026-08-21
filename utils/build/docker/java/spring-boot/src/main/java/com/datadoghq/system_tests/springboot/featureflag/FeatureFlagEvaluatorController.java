package com.datadoghq.system_tests.springboot.featureflag;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

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
import java.util.concurrent.TimeUnit;

@RestController
public class FeatureFlagEvaluatorController {

    private static final String DEPLOYMENT_MODE = System.getenv().getOrDefault("SYSTEM_TESTS_JAVA_OPENFEATURE_MODE", "explicit");
    private static volatile String providerName = "uninitialized";

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
                provider = "ssi".equalsIgnoreCase(DEPLOYMENT_MODE)
                        ? api.getProvider()
                        : createDatadogProvider();
            } else {
                provider = new NoOpProvider() {
                    @Override
                    public ProviderState getState() {
                        return ProviderState.READY;
                    }
                };
            }
            if (!"ssi".equalsIgnoreCase(DEPLOYMENT_MODE)) {
                api.setProviderAndWait(provider);
            }
            providerName = api.getProviderMetadata().getName();
            final Client client = api.getClient();
            if ("ssi".equalsIgnoreCase(DEPLOYMENT_MODE)) {
                waitForInjectedProvider(client);
            }
            return client;
        }

        private static void waitForInjectedProvider(final Client client) {
            final long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(10);
            while (client.getProviderState() == ProviderState.NOT_READY && System.nanoTime() < deadline) {
                try {
                    TimeUnit.MILLISECONDS.sleep(25);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    throw new IllegalStateException("Interrupted while waiting for the injected provider", e);
                }
            }
            if (client.getProviderState() != ProviderState.READY) {
                throw new IllegalStateException("Injected provider did not become ready: " + client.getProviderState());
            }
        }

        private static FeatureProvider createDatadogProvider() {
            try {
                final Class<?> providerClass = Class.forName("datadog.trace.api.openfeature.Provider");
                return (FeatureProvider) providerClass.getConstructor().newInstance();
            } catch (ReflectiveOperationException e) {
                throw new IllegalStateException("Datadog OpenFeature provider is not on the application classpath", e);
            }
        }
    }

    private static final Logger LOGGER = LoggerFactory.getLogger(FeatureFlagEvaluatorController.class);

    @Autowired
    @Lazy
    private Client client;

    @PostMapping(value = "/ffe", consumes = APPLICATION_JSON_VALUE, produces = APPLICATION_JSON_VALUE)
    public ResponseEntity<Map<String, Object>> evaluate(@RequestBody final EvaluateRequest request) {
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
        result.put("deploymentMode", DEPLOYMENT_MODE);
        result.put("provider", providerName);
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
