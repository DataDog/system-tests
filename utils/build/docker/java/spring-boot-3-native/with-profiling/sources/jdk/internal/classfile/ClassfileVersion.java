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

import jdk.internal.classfile.impl.ClassfileVersionImpl;

/**
 * Models the classfile version information for a class.  Delivered as a {@link
 * jdk.internal.classfile.ClassElement} when traversing the elements of a {@link
 * ClassModel}.
 */
public sealed interface ClassfileVersion
        extends ClassElement
        permits ClassfileVersionImpl {
    /**
     * {@return the major classfile version}
     */
    int majorVersion();

    /**
     * {@return the minor classfile version}
     */
    int minorVersion();

    /**
     * {@return a {@link ClassfileVersion} element}
     * @param majorVersion the major classfile version
     * @param minorVersion the minor classfile version
     */
    static ClassfileVersion of(int majorVersion, int minorVersion) {
        return new ClassfileVersionImpl(majorVersion, minorVersion);
    }
}
