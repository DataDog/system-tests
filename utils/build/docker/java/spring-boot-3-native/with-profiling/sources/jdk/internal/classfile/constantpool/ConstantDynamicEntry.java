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

import jdk.internal.classfile.TypeKind;
import jdk.internal.classfile.impl.Util;
import java.lang.constant.ConstantDesc;
import java.lang.constant.DynamicConstantDesc;

import jdk.internal.classfile.impl.AbstractPoolEntry;

/**
 * Models a {@code CONSTANT_Dynamic_info} constant in the constant pool of a
 * classfile.
 */
public sealed interface ConstantDynamicEntry
        extends DynamicConstantPoolEntry, LoadableConstantEntry
        permits AbstractPoolEntry.ConstantDynamicEntryImpl {

    @Override
    default ConstantDesc constantValue() {
        return asSymbol();
    }

    /**
     * {@return the symbolic descriptor for the {@code invokedynamic} constant}
     */
    default DynamicConstantDesc<?> asSymbol() {
        return DynamicConstantDesc.ofNamed(bootstrap().bootstrapMethod().asSymbol(),
                                           name().stringValue(),
                                           Util.fieldTypeSymbol(nameAndType()),
                                           bootstrap().arguments().stream()
                                                      .map(LoadableConstantEntry::constantValue)
                                                      .toArray(ConstantDesc[]::new));
    }

    /**
     * {@return the type of the constant}
     */
    @Override
    default TypeKind typeKind() {
        return TypeKind.fromDescriptor(type().stringValue());
    }
}
