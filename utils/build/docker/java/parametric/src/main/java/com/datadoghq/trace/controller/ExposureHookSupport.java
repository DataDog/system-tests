package com.datadoghq.trace.controller;

import dev.openfeature.sdk.EvaluationContext;
import dev.openfeature.sdk.FlagEvaluationDetails;
import dev.openfeature.sdk.FlagEvaluationOptions;
import dev.openfeature.sdk.Hook;
import dev.openfeature.sdk.HookContext;
import dev.openfeature.sdk.Value;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Consumer;

/** Adapts the public Datadog exposure hook to the shared parametric response. */
final class ExposureHookSupport {
    private ExposureHookSupport() {}

    static FlagEvaluationOptions options(List<Map<String, Object>> rows, boolean failAfter) {
        final var builder = FlagEvaluationOptions.builder();
        if (failAfter) {
            // After hooks run in reverse order. Reject after the exposure hooks' After stage.
            builder.hook(new Hook<Object>() {
                @Override
                public void after(HookContext<Object> context, FlagEvaluationDetails<Object> details,
                                  Map<String, Object> hints) {
                    throw new IllegalStateException("application rejected the flag result");
                }
            });
        }
        for (int id = 0; id < 2; id++) {
            builder.hook(createHook(rows, id));
        }
        return builder.build();
    }

    private static Hook<?> createHook(List<Map<String, Object>> rows, int id) {
        // Older dd-openfeature versions must still compile and run unrelated parametric tests.
        // Resolve the real public API only when this test requests exposure observations.
        try {
            final Class<?> hookClass = Class.forName("datadog.trace.api.openfeature.ExposureHook");
            final Consumer<Object> callback = evaluation -> rows.add(observation(evaluation, id));
            return (Hook<?>) hookClass.getConstructor(Consumer.class).newInstance(callback);
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException("The loaded dd-openfeature does not support ExposureHook", e);
        }
    }

    private static Map<String, Object> observation(Object evaluation, int id) {
        try {
            final Class<?> type = evaluation.getClass();
            final FlagEvaluationDetails<?> details =
                    (FlagEvaluationDetails<?>) type.getMethod("getDetails").invoke(evaluation);
            final EvaluationContext context =
                    (EvaluationContext) type.getMethod("getContext").invoke(evaluation);
            final Map<String, Object> row = new HashMap<>();
            row.put("hook", id);
            row.put("flag", details.getFlagKey());
            row.put("subject", context.getTargetingKey());
            row.put("variant", details.getVariant());
            final var metadata = details.getFlagMetadata() == null
                    ? Map.of() : details.getFlagMetadata().asUnmodifiableMap();
            row.put("metadata", metadata);
            row.put("allocationKey", metadata.get("allocationKey"));
            row.put("value", details.getValue() instanceof Value
                    ? context.convertValue((Value) details.getValue()) : details.getValue());
            row.put("errorCode", details.getErrorCode() == null ? "" : details.getErrorCode().name());
            row.put("reason", details.getReason());
            row.put("isExposure", type.getMethod("isExposure").invoke(evaluation));
            row.put("isCacheHit", type.getMethod("isCacheHit").invoke(evaluation));
            row.put("shouldSend", type.getMethod("shouldSend").invoke(evaluation));
            row.put("features", type.getMethod("getFeatures").invoke(evaluation));
            return row;
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException("Could not read the public ExposureHook evaluation", e);
        }
    }
}
