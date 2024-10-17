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
package jdk.internal.misc;

/**
 * Defines static methods to test if preview features are enabled at run-time.
 */
public class PreviewFeatures {
    private static final boolean ENABLED = isPreviewEnabled();

    private PreviewFeatures() {
    }

    /**
     * {@return true if preview features are enabled, otherwise false}
     */
    public static boolean isEnabled() {
        return ENABLED;
    }

    /**
     * Ensures that preview features are enabled.
     * @throws UnsupportedOperationException if preview features are not enabled
     */
    public static void ensureEnabled() {
        if (!isEnabled()) {
            throw new UnsupportedOperationException(
                "Preview Features not enabled, need to run with --enable-preview");
        }
    }

    private static native boolean isPreviewEnabled();
}
