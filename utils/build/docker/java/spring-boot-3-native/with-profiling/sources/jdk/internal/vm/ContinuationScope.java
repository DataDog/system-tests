/*
 * Copyright (c) 2018, 2022, Oracle and/or its affiliates. All rights reserved.
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

package jdk.internal.vm;

import java.util.Objects;

/**
 * A Continuation scope.
 */
public class ContinuationScope {
    final String name;

    /**
     * Constructs a new scope.
     * @param name The scope's name
     */
    public ContinuationScope(String name) {
        this.name = Objects.requireNonNull(name);
    }

    /**
     * A constructor providing no name is available to subclasses.
     */
    protected ContinuationScope() {
        this.name = getClass().getName();
    }

    /**
     * Returns this scope's name.
     * @return this scope's name
     */
    public final String getName() {
        return name;
    }

    @Override
    public final String toString() {
        return name;
    }

    @Override
    public final int hashCode() {
        return super.hashCode();
    }

    @Override
    public final boolean equals(Object obj) {
        return super.equals(obj);
    }
}
