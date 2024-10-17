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

import jdk.jfr.internal.LongMap;
import jdk.jfr.internal.Type;

/**
 * Holds the chunk global state of constants
 */
final class Constants {
    private final LongMap<PoolEntry> table = new LongMap<>();
    private final Type type;

    public Constants(Type type) {
        this.type = type;
    }

    public void add(long key, PoolEntry entry) {
        table.put(key, entry);
    }

    public PoolEntry get(long key) {
        return table.get(key);
    }

    public String toString() {
        return "Pool: " + type.getName() + " size = " + table.size();
    }
}