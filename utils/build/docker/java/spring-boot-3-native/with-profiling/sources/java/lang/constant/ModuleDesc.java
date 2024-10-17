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
 * A nominal descriptor for a {@code Module} constant.
 *
 * <p>
 * To create a {@link ModuleDesc} for a module, use the {@link #of(String)}
 * method.
 *
 * @jvms 4.4.11 The CONSTANT_Module_info Structure
 * @since 21
 */
public sealed interface ModuleDesc
        permits ModuleDescImpl {

    /**
     * Returns a {@link ModuleDesc} for a module,
     * given the name of the module.
     *
     * @param name the module name
     * @return a {@link ModuleDesc} describing the desired module
     * @throws NullPointerException if the argument is {@code null}
     * @throws IllegalArgumentException if the name string is not in the
     * correct format
     * @jvms 4.2.3 Module and Package Names
     */
    static ModuleDesc of(String name) {
        ConstantUtils.validateModuleName(requireNonNull(name));
        return new ModuleDescImpl(name);
    }

    /**
     * Returns the module name of this {@link ModuleDesc}.
     *
     * @return the module name
     */
    String name();

    /**
     * Compare the specified object with this descriptor for equality.
     * Returns {@code true} if and only if the specified object is
     * also a {@link ModuleDesc} and both describe the same module.
     *
     * @param o the other object
     * @return whether this descriptor is equal to the other object
     */
    @Override
    boolean equals(Object o);
}
