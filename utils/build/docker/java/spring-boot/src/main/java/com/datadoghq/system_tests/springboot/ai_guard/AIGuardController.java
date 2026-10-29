package com.datadoghq.system_tests.springboot.ai_guard;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.core.JsonGenerator;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.JsonSerializer;
import com.fasterxml.jackson.databind.SerializerProvider;
import datadog.trace.api.aiguard.AIGuard;
import datadog.trace.api.aiguard.AIGuard.Evaluation;
import datadog.trace.api.interceptor.MutableSpan;
import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;
import org.springframework.boot.autoconfigure.jackson.Jackson2ObjectMapperBuilderCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;


@RestController
public class AIGuardController {

    @Configuration
    public static class JacksonConfig {
        @Bean
        public Jackson2ObjectMapperBuilderCustomizer mixInCustomizer() {
            return builder -> builder
                    .mixIn(AIGuard.AIGuardAbortError.class, AIGuardAbortErrorMixIn.class)
                    .mixIn(AIGuard.Evaluation.class, AIGuardEvaluationMixIn.class)
                    .serializerByType(AIGuard.Message.class, new MessageSerializer());
        }
    }

    @PostMapping("/ai_guard/evaluate")
    public ResponseEntity<?> evaluate(
            @RequestHeader(name = "X-AI-Guard-Block", defaultValue = "false") final boolean block,
            @RequestHeader(name = "X-User-Id", required = false) final String userId,
            @RequestHeader(name = "X-Session-Id", required = false) final String sessionId,
            @RequestBody final List<Message> data) {
        final Span activeSpan = GlobalTracer.get().activeSpan();
        if (activeSpan instanceof MutableSpan) {
            final MutableSpan rootSpan = ((MutableSpan) activeSpan).getLocalRootSpan();
            if (userId != null && !userId.isEmpty()) {
                rootSpan.setTag("usr.id", userId);
            }
            if (sessionId != null && !sessionId.isEmpty()) {
                rootSpan.setTag("usr.session_id", sessionId);
            }
        }
        try {
            final List<AIGuard.Message> messages = data.stream().map(Message::toAIGuard).collect(Collectors.toList());
            final Evaluation result = AIGuard.evaluate(messages, new AIGuard.Options().block(block));
            return ResponseEntity.ok(result);
        } catch (AIGuard.AIGuardAbortError error) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body(error);
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(e);
        }
    }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    public static class Message {
        @JsonProperty("role")
        private String role;

        @JsonProperty("content")
        private JsonNode content;  // Can be String or Array of content parts

        @JsonProperty("tool_calls")
        private List<ToolCall> toolCalls;

        @JsonProperty("tool_call_id")
        private String toolCallId;

        @JsonProperty("name")
        private String name;

        public Message() {}

        public Message(String role, String content) {
            this.role = role;
            this.content = null;  // Will be handled by Jackson
        }

        public String getRole() {
            return role;
        }

        public void setRole(String role) {
            this.role = role;
        }

        public JsonNode getContent() {
            return content;
        }

        public void setContent(JsonNode content) {
            this.content = content;
        }

        public List<ToolCall> getToolCalls() {
            return toolCalls;
        }

        public void setToolCalls(List<ToolCall> toolCalls) {
            this.toolCalls = toolCalls;
        }

        public String getToolCallId() {
            return toolCallId;
        }

        public void setToolCallId(String toolCallId) {
            this.toolCallId = toolCallId;
        }

        public String getName() {
            return name;
        }

        public void setName(String name) {
            this.name = name;
        }

        public AIGuard.Message toAIGuard() {
            // Every field is carried over independently: an assistant message can hold content
            // *and* tool calls at the same time, and dropping either half would change the
            // conversation the tracer sends to the AI Guard service.
            List<AIGuard.ToolCall> calls = toolCalls == null || toolCalls.isEmpty()
                    ? null
                    : toolCalls.stream().map(ToolCall::toAIGuard).collect(Collectors.toList());

            if (content != null && content.isArray()) {
                // Content parts format
                List<AIGuard.ContentPart> parts = new ArrayList<>();
                for (JsonNode partNode : content) {
                    String type = partNode.get("type").asText();
                    if ("text".equals(type)) {
                        parts.add(AIGuard.ContentPart.text(partNode.get("text").asText()));
                    } else if ("image_url".equals(type)) {
                        String url = partNode.get("image_url").get("url").asText();
                        parts.add(AIGuard.ContentPart.imageUrl(url));
                    }
                }
                return new AIGuard.Message(role, parts, calls, toolCallId);
            }
            // String content format
            String contentStr = content != null && content.isTextual() ? content.asText() : null;
            return new AIGuard.Message(role, contentStr, calls, toolCallId);
        }
    }

    public static class ToolCall {
        @JsonProperty("id")
        private String id;

        @JsonProperty("type")
        private String type;

        @JsonProperty("function")
        private Function function;

        public String getId() {
            return id;
        }

        public void setId(String id) {
            this.id = id;
        }

        public String getType() {
            return type;
        }

        public void setType(String type) {
            this.type = type;
        }

        public Function getFunction() {
            return function;
        }

        public void setFunction(Function function) {
            this.function = function;
        }

        public AIGuard.ToolCall toAIGuard() {
            return AIGuard.ToolCall.toolCall(id, function.getName(), function.getArguments());
        }
    }

    public static class Function {
        @JsonProperty("name")
        private String name;

        @JsonProperty("arguments")
        private String arguments;

        public String getName() {
            return name;
        }

        public void setName(String name) {
            this.name = name;
        }

        public String getArguments() {
            return arguments;
        }

        public void setArguments(String arguments) {
            this.arguments = arguments;
        }
    }

    public static abstract class AIGuardAbortErrorMixIn {

        @JsonProperty("tag_probs")
        abstract Object getTagProbabilities();
    }

    public static abstract class AIGuardEvaluationMixIn {

        @JsonProperty("tag_probs")
        abstract Object getTagProbabilities();

        @JsonProperty("redaction_replacements")
        abstract Object getRedactionReplacements();
    }

    /**
     * Writes {@link AIGuard.Message} back in the very shape the request carried it.
     *
     * <p>Bean serialization would emit the SDK's field names and a null for every field the
     * message does not use, which no other tracer's weblog does and which makes the response
     * impossible to compare against the messages that were sent. Content parts live under
     * {@code content} as an array, exactly like the OpenAI wire format the SDK models.
     */
    public static class MessageSerializer extends JsonSerializer<AIGuard.Message> {

        @Override
        public void serialize(final AIGuard.Message message,
                              final JsonGenerator gen,
                              final SerializerProvider serializers) throws IOException {
            gen.writeStartObject();
            if (message.getRole() != null) {
                gen.writeStringField("role", message.getRole());
            }
            if (message.getContentParts() != null) {
                gen.writeFieldName("content");
                gen.writeStartArray();
                for (final AIGuard.ContentPart part : message.getContentParts()) {
                    writeContentPart(part, gen);
                }
                gen.writeEndArray();
            } else if (message.getContent() != null) {
                // Written on nullness, not emptiness: "" is the redaction remove strategy.
                gen.writeStringField("content", message.getContent());
            }
            if (message.getToolCalls() != null) {
                gen.writeFieldName("tool_calls");
                gen.writeStartArray();
                for (final AIGuard.ToolCall toolCall : message.getToolCalls()) {
                    writeToolCall(toolCall, gen);
                }
                gen.writeEndArray();
            }
            if (message.getToolCallId() != null) {
                gen.writeStringField("tool_call_id", message.getToolCallId());
            }
            gen.writeEndObject();
        }

        private static void writeContentPart(final AIGuard.ContentPart part,
                                             final JsonGenerator gen) throws IOException {
            gen.writeStartObject();
            gen.writeStringField("type", part.getType().toString());
            if (part.getType() == AIGuard.ContentPart.Type.TEXT) {
                gen.writeStringField("text", part.getText());
            } else if (part.getType() == AIGuard.ContentPart.Type.IMAGE_URL) {
                gen.writeFieldName("image_url");
                gen.writeStartObject();
                gen.writeStringField("url", part.getImageUrl().getUrl());
                gen.writeEndObject();
            }
            gen.writeEndObject();
        }

        private static void writeToolCall(final AIGuard.ToolCall toolCall,
                                          final JsonGenerator gen) throws IOException {
            gen.writeStartObject();
            if (toolCall.getId() != null) {
                gen.writeStringField("id", toolCall.getId());
            }
            final AIGuard.ToolCall.Function function = toolCall.getFunction();
            if (function != null) {
                gen.writeFieldName("function");
                gen.writeStartObject();
                if (function.getName() != null) {
                    gen.writeStringField("name", function.getName());
                }
                if (function.getArguments() != null) {
                    gen.writeStringField("arguments", function.getArguments());
                }
                gen.writeEndObject();
            }
            gen.writeEndObject();
        }
    }

}
