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

package jdk.internal.util;

/**
 * Implementations of this class provide information necessary to
 * assist {@link java.lang.invoke.StringConcatFactory} perform optimal
 * insertion.
 *
 * @since 21
 *
 * Warning: This class is part of PreviewFeature.Feature.STRING_TEMPLATES.
 *          Do not rely on its availability.
 */
public interface FormatConcatItem {
    /**
     * Calculate the length of the insertion.
     *
     * @param lengthCoder current value of the length + coder
     * @return adjusted value of the length + coder
     */
    long mix(long lengthCoder);

    /**
     * Insert content into buffer prior to the current length.
     *
     * @param lengthCoder current value of the length + coder
     * @param buffer      buffer to append to
     *
     * @return adjusted value of the length + coder
     *
     * @throws Throwable if fails to prepend value (unusual).
     */
    long prepend(long lengthCoder, byte[] buffer) throws Throwable;
}
