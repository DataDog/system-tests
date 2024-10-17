/*
 * Copyright (c) 2023, Oracle and/or its affiliates. All rights reserved.
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
package jdk.jfr.internal.periodic;

/**
 * Lookup key that can safely be used in a {@code Map}.
 * <p>
 * {@code Runnable} objects can't be used with {@code LinkedHashMap} as it
 * invokes {@code hashCode} and {@code equals}, for example when resizing the
 * {@code Map}, possibly in a non-secure context.
 * <p>
 * {@code IdentityHashMap} can't be used as it will not preserve order.
 */
final class LookupKey {
    private final Object object;

    public LookupKey(Object object) {
        this.object = object;
    }

    public int hashCode() {
        return System.identityHashCode(object);
    }

    public boolean equals(Object that) {
        if (that instanceof LookupKey lookupKey) {
            return lookupKey.object == object;
        }
        return false;
    }
}