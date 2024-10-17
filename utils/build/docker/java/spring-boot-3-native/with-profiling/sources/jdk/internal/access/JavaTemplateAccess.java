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

package jdk.internal.access;

import java.util.List;

public interface JavaTemplateAccess {

    /**
     * Returns a StringTemplate composed from fragments and values.
     *
     * @implSpec The {@code fragments} list size must be one more that the
     * {@code values} list size.
     *
     * @param fragments list of string fragments
     * @param values    list of expression values
     *
     * @return StringTemplate composed from fragments and values
     *
     * @throws IllegalArgumentException if fragments list size is not one more
     *         than values list size
     * @throws NullPointerException if fragments is null or values is null or if any fragment is null.
     *
     * @implNote Contents of both lists are copied to construct immutable lists.
     */
    StringTemplate of(List<String> fragments, List<?> values);

    /**
     * Creates a string that interleaves the elements of values between the
     * elements of fragments.
     *
     * @param fragments  list of String fragments
     * @param values     list of expression values
     *
     * @return String interpolation of fragments and values
     */
    String interpolate(List<String> fragments, List<?> values);

    /**
     * Combine one or more {@link StringTemplate StringTemplates} to produce a combined {@link StringTemplate}.
     * {@snippet :
     * StringTemplate st = StringTemplate.combine("\{a}", "\{b}", "\{c}");
     * assert st.interpolate().equals("\{a}\{b}\{c}");
     * }
     *
     * @param sts  zero or more {@link StringTemplate}
     *
     * @return combined {@link StringTemplate}
     *
     * @throws NullPointerException if sts is null or if any element of sts is null
     */
    StringTemplate combine(StringTemplate... sts);

}

