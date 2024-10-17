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

import jdk.internal.classfile.constantpool.ClassEntry;
import jdk.internal.classfile.impl.SuperclassImpl;

/**
 * Models the superclass of a class.  Delivered as a {@link
 * jdk.internal.classfile.ClassElement} when traversing a {@link ClassModel}.
 */
public sealed interface Superclass
        extends ClassElement
        permits SuperclassImpl {

    /** {@return the superclass} */
    ClassEntry superclassEntry();

    /**
     * {@return a {@linkplain Superclass} element}
     * @param superclassEntry the superclass
     */
    static Superclass of(ClassEntry superclassEntry) {
        return new SuperclassImpl(superclassEntry);
    }
}
