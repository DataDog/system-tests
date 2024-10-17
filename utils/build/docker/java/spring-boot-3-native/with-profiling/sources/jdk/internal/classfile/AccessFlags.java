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
package jdk.internal.classfile;

import java.util.Set;
import jdk.internal.classfile.impl.AccessFlagsImpl;
import java.lang.reflect.AccessFlag;

/**
 * Models the access flags for a class, method, or field.  Delivered as a
 *  {@link jdk.internal.classfile.ClassElement}, {@link jdk.internal.classfile.FieldElement}, or
 *  {@link jdk.internal.classfile.MethodElement} when traversing
 *  the corresponding model type.
 */
public sealed interface AccessFlags
        extends ClassElement, MethodElement, FieldElement
        permits AccessFlagsImpl {

    /**
     * {@return the access flags, as a bit mask}
     */
    int flagsMask();

    /**
     * {@return the access flags}
     */
    Set<AccessFlag> flags();

    /**
     * {@return whether the specified flag is present}  The specified flag
     * should be a valid flag for the classfile location associated with this
     * element otherwise false is returned.
     * @param flag the flag to test
     */
    boolean has(AccessFlag flag);

    /**
     * {@return the classfile location for this element, which is either class,
     * method, or field}
     */
    AccessFlag.Location location();

    /**
     * {@return an {@linkplain AccessFlags} for a class}
     * @param mask the flags to be set, as a bit mask
     */
    static AccessFlags ofClass(int mask) {
        return new AccessFlagsImpl(AccessFlag.Location.CLASS, mask);
    }

    /**
     * {@return an {@linkplain AccessFlags} for a class}
     * @param flags the flags to be set
     */
    static AccessFlags ofClass(AccessFlag... flags) {
        return new AccessFlagsImpl(AccessFlag.Location.CLASS, flags);
    }

    /**
     * {@return an {@linkplain AccessFlags} for a field}
     * @param mask the flags to be set, as a bit mask
     */
    static AccessFlags ofField(int mask) {
        return new AccessFlagsImpl(AccessFlag.Location.FIELD, mask);
    }

    /**
     * {@return an {@linkplain AccessFlags} for a field}
     * @param flags the flags to be set
     */
    static AccessFlags ofField(AccessFlag... flags) {
        return new AccessFlagsImpl(AccessFlag.Location.FIELD, flags);
    }

    /**
     * {@return an {@linkplain AccessFlags} for a method}
     * @param mask the flags to be set, as a bit mask
     */
    static AccessFlags ofMethod(int mask) {
        return new AccessFlagsImpl(AccessFlag.Location.METHOD, mask);
    }

    /**
     * {@return an {@linkplain AccessFlags} for a method}
     * @param flags the flags to be set
     */
    static AccessFlags ofMethod(AccessFlag... flags) {
        return new AccessFlagsImpl(AccessFlag.Location.METHOD, flags);
    }
}
