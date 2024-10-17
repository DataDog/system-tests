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
import java.lang.constant.DirectMethodHandleDesc;

import jdk.internal.classfile.impl.AbstractPoolEntry;

/**
 * Models a {@code CONSTANT_MethodHandle_info} constant in the constant pool of a
 * classfile.
 */
public sealed interface MethodHandleEntry
        extends LoadableConstantEntry
        permits AbstractPoolEntry.MethodHandleEntryImpl {

    @Override
    default ConstantDesc constantValue() {
        return asSymbol();
    }

    /**
     * {@return the reference kind of this method handle {@jvms 4.4.8}}
     * @see java.lang.invoke.MethodHandleInfo
     */
    int kind();

    /**
     * {@return the constant pool entry describing the method}
     */
    MemberRefEntry reference();

    /**
     * {@return a symbolic descriptor for this method handle}
     */
    DirectMethodHandleDesc asSymbol();
}
