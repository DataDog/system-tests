/*
 * Copyright (c) 2022, Oracle and/or its affiliates. All rights reserved.
 * ORACLE PROPRIETARY/CONFIDENTIAL. Use is subject to license terms.
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 */
package jdk.jfr.internal.consumer.filter;

import jdk.jfr.internal.Type;

/**
 * Represents the binary content of constant pool, both key and value.
 * <p>
 * All positional values are relative to file start, not the chunk.
 */
final class PoolEntry {
    private final long startPosition;
    private final long endPosition;
    private final Type type;
    private final long keyId;
    private final Object references;

    private boolean touched;

    PoolEntry(long startPosition, long endPosition, Type type, long keyId, Object references) {
        this.startPosition = startPosition;
        this.endPosition = endPosition;
        this.type = type;
        this.keyId = keyId;
        this.references = references;
    }

    public void touch() {
        this.touched = true;
    }

    public boolean isTouched() {
        return touched;
    }

    public Object getReferences() {
        return references;
    }

    public long getStartPosition() {
        return startPosition;
    }

    public long getEndPosition() {
        return endPosition;
    }

    public Type getType() {
        return type;
    }

    public long getId() {
        return keyId;
    }

    public String toString() {
        StringBuilder sb = new StringBuilder();
        sb.append("start: ").append(startPosition).append("\n");
        sb.append("end: ").append(endPosition).append("\n");
        sb.append("type: ").append(type).append(" (").append(type.getId()).append(")\n");
        sb.append("key: ").append(keyId).append("\n");
        sb.append("object: ").append(references).append("\n");
        return sb.toString();
    }
}