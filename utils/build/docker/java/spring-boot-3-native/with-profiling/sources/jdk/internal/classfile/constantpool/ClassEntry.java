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
package jdk.internal.classfile.constantpool;

import java.lang.constant.ClassDesc;
import java.lang.constant.ConstantDesc;
import jdk.internal.classfile.impl.AbstractPoolEntry;

/**
 * Models a {@code CONSTANT_Class_info} constant in the constant pool of a
 * classfile.
 */
public sealed interface ClassEntry
        extends LoadableConstantEntry
        permits AbstractPoolEntry.ClassEntryImpl {

    @Override
    default ConstantDesc constantValue() {
        return asSymbol();
    }

    /**
     * {@return the UTF8 constant pool entry for the class name}
     */
    Utf8Entry name();

    /**
     * {@return the class name, as an internal binary name}
     */
    String asInternalName();

    /**
     * {@return the class name, as a symbolic descriptor}
     */
    ClassDesc asSymbol();
}
