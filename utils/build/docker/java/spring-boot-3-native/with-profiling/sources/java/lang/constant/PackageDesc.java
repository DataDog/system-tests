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
package java.lang.constant;

import static java.util.Objects.requireNonNull;

/**
 * A nominal descriptor for a {@code Package} constant.
 *
 * <p>
 * To create a {@link PackageDesc} for a package,
 * use the {@link #of(String)} or {@link #ofInternalName(String)} method.
 *
 * @jvms 4.4.12 The CONSTANT_Package_info Structure
 * @since 21
 */
public sealed interface PackageDesc
        permits PackageDescImpl {

    /**
     * Returns a {@link PackageDesc} for a package,
     * given the name of the package, such as {@code "java.lang"}.
     *
     * @param name the fully qualified (dot-separated) package name
     * @return a {@link PackageDesc} describing the desired package
     * @throws NullPointerException if the argument is {@code null}
     * @throws IllegalArgumentException if the name string is not in the
     * correct format
     * @jls 6.5.3 Module Names and Package Names
     * @see PackageDesc#ofInternalName(String)
     */
    static PackageDesc of(String name) {
        ConstantUtils.validateBinaryPackageName(requireNonNull(name));
        return new PackageDescImpl(ConstantUtils.binaryToInternal(name));
    }

    /**
     * Returns a {@link PackageDesc} for a package,
     * given the name of the package in internal form,
     * such as {@code "java/lang"}.
     *
     * @param name the fully qualified package name, in internal
     * (slash-separated) form
     * @return a {@link PackageDesc} describing the desired package
     * @throws NullPointerException if the argument is {@code null}
     * @throws IllegalArgumentException if the name string is not in the
     * correct format
     * @jvms 4.2.1 Binary Class and Interface Names
     * @jvms 4.2.3 Module and Package Names
     * @see PackageDesc#of(String)
     */
    static PackageDesc ofInternalName(String name) {
        ConstantUtils.validateInternalPackageName(requireNonNull(name));
        return new PackageDescImpl(name);
    }

    /**
     * Returns the fully qualified (slash-separated) package name in internal form
     * of this {@link PackageDesc}.
     *
     * @return the package name in internal form, or the empty string for the
     * unnamed package
     * @see PackageDesc#name()
     */
    String internalName();

    /**
     * Returns the fully qualified (dot-separated) package name
     * of this {@link PackageDesc}.
     *
     * @return the package name, or the empty string for the
     * unnamed package
     * @see PackageDesc#internalName()
     */
    default String name() {
        return ConstantUtils.internalToBinary(internalName());
    }

    /**
     * Compare the specified object with this descriptor for equality.
     * Returns {@code true} if and only if the specified object is
     * also a {@link PackageDesc} and both describe the same package.
     *
     * @param o the other object
     * @return whether this descriptor is equal to the other object
     */
    @Override
    boolean equals(Object o);
}
