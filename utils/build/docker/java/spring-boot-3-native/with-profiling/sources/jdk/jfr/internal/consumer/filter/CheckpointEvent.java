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

import java.util.Collection;
import java.util.LinkedHashMap;

import jdk.jfr.internal.Type;

/**
 * Represents a checkpoint event.
 * <p>
 * All positional values are relative to file start, not the chunk.
 */
public final class CheckpointEvent {
    private final ChunkWriter chunkWriter;
    private final LinkedHashMap<Long, CheckpointPool> pools = new LinkedHashMap<>();
    private final long startPosition;

    public CheckpointEvent(ChunkWriter chunkWriter, long startPosition) {
        this.chunkWriter = chunkWriter;
        this.startPosition = startPosition;
    }

    public PoolEntry addEntry(Type type, long id, long startPosition, long endPosition, Object references) {
        long typeId = type.getId();
        PoolEntry pe = new PoolEntry(startPosition, endPosition, type, id, references);
        var cpp = pools.computeIfAbsent(typeId, k -> new CheckpointPool(typeId));
        cpp.add(pe);
        chunkWriter.getPool(type).add(id, pe);
        return pe;
    }

    public long touchedPools() {
        int count = 0;
        for (CheckpointPool cpp : pools.values()) {
            if (cpp.isTouched()) {
                count++;
            }
        }
        return count;
    }

    public Collection<CheckpointPool> getPools() {
        return pools.values();
    }

    public long getStartPosition() {
        return startPosition;
    }

    public String toString() {
        StringBuilder sb = new StringBuilder();
        for (CheckpointPool p : pools.values()) {
            for (var e : p.getEntries()) {
                if (e.isTouched()) {
                    sb.append(e.getType().getName() + " " + e.getId() + "\n");
                }
            }
        }
        return sb.toString();
    }
}