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
package jdk.internal.vm;

/**
 * Defines a static method to test if the VM has continuations support.
 */
public class ContinuationSupport {
    private static final boolean SUPPORTED = isSupported0();

    private ContinuationSupport() {
    }

    /**
     * Return true if the VM has continuations support.
     */
    public static boolean isSupported() {
        return SUPPORTED;
    }

    /**
     * Ensures that VM has continuations support.
     * @throws UnsupportedOperationException if not supported
     */
    public static void ensureSupported() {
        if (!isSupported()) {
            throw new UnsupportedOperationException("VM does not support continuations");
        }
    }

    private static native boolean isSupported0();
}
