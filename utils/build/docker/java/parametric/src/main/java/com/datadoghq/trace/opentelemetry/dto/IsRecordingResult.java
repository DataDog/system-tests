package com.datadoghq.trace.opentelemetry.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record IsRecordingResult(@JsonProperty("is_recording") boolean isRecording) {
}
