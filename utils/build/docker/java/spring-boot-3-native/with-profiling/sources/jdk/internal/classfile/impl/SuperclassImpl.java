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
package jdk.internal.classfile.impl;

import jdk.internal.classfile.constantpool.ClassEntry;
import jdk.internal.classfile.Superclass;

import static java.util.Objects.requireNonNull;

public final class SuperclassImpl
        extends AbstractElement
        implements Superclass {
    private final ClassEntry superclassEntry;

    public SuperclassImpl(ClassEntry superclassEntry) {
        requireNonNull(superclassEntry);
        this.superclassEntry = superclassEntry;
    }

    @Override
    public ClassEntry superclassEntry() {
        return superclassEntry;
    }

    @Override
    public void writeTo(DirectClassBuilder builder) {
        builder.setSuperclass(superclassEntry);
    }

    @Override
    public String toString() {
        return String.format("Superclass[superclassEntry=%s]", superclassEntry.name().stringValue());
    }
}
