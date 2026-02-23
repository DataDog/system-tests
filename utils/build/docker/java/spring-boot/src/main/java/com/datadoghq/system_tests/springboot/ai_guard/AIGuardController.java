package com.datadoghq.system_tests.springboot.ai_guard;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import datadog.trace.api.aiguard.AIGuard;
import datadog.trace.api.aiguard.AIGuard.Evaluation;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;


@RestController
public class AIGuardController {

    @PostMapping("/ai_guard/evaluate")
    public ResponseEntity<?> evaluate(
            @RequestHeader(name = "X-AI-Guard-Block", defaultValue = "false") final boolean block,
            @RequestBody final List<Message> data) {
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
            if (toolCallId != null) {
                String contentStr = content != null && content.isTextual() ? content.asText() : null;
                return AIGuard.Message.tool(toolCallId, contentStr);
            }
            if (toolCalls != null && !toolCalls.isEmpty()) {
                return AIGuard.Message.assistant(
                        toolCalls.stream().map(ToolCall::toAIGuard).toArray(AIGuard.ToolCall[]::new));
            }
            // Handle content parts vs string content
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
                return AIGuard.Message.message(role, parts);
            } else {
                // String content format
                String contentStr = content != null && content.isTextual() ? content.asText() : null;
                return AIGuard.Message.message(role, contentStr);
            }
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

}
