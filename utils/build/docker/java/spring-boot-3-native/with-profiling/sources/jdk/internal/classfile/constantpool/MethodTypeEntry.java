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

import java.lang.constant.ConstantDesc;
import java.lang.constant.MethodTypeDesc;

import jdk.internal.classfile.impl.AbstractPoolEntry;

/**
 * Models a {@code CONSTANT_MethodType_info} constant in the constant pool of a
 * classfile.
 */
public sealed interface MethodTypeEntry
        extends LoadableConstantEntry
        permits AbstractPoolEntry.MethodTypeEntryImpl {

    @Override
    default ConstantDesc constantValue() {
        return asSymbol();
    }

    /**
     * {@return the constant pool entry describing the method type}
     */
    Utf8Entry descriptor();

    /**
     * {@return a symbolic descriptor for the method type}
     */
    MethodTypeDesc asSymbol();
}
