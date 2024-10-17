/*
 * Copyright (c) 2016, 2022, Oracle and/or its affiliates. All rights reserved.
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

package jdk.jfr.internal.consumer;

import jdk.jfr.internal.Type;

/**
 * A temporary placeholder, so objects can reference themselves (directly, or
 * indirectly), when making a transition from numeric id references to Java
 * object references.
 */
public record Reference(ConstantMap pool, long key) {

    Object resolve() {
        return pool.get(key);
    }

    public Type type() {
        return pool.getType();
    }

    @Override
    public String toString() {
        return "ref: " + pool.getName() + "[" + key + "]";
    }
}