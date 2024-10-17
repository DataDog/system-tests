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
package jdk.internal.classfile.instruction;

import jdk.internal.classfile.CodeElement;
import jdk.internal.classfile.CodeModel;
import jdk.internal.classfile.constantpool.ClassEntry;
import jdk.internal.classfile.Instruction;
import jdk.internal.classfile.impl.AbstractInstruction;

/**
 * Models a {@code multianewarray} invocation instruction in the {@code code}
 * array of a {@code Code} attribute.  Delivered as a {@link CodeElement}
 * when traversing the elements of a {@link CodeModel}.
 */
public sealed interface NewMultiArrayInstruction extends Instruction
        permits AbstractInstruction.BoundNewMultidimensionalArrayInstruction,
                AbstractInstruction.UnboundNewMultidimensionalArrayInstruction {

    /**
     * {@return the type of the array, as a symbolic descriptor}
     */
    ClassEntry arrayType();

    /**
     * {@return the number of dimensions of the aray}
     */
    int dimensions();

    /**
     * {@return a new multi-dimensional array instruction}
     *
     * @param arrayTypeEntry the type of the array
     * @param dimensions the number of dimensions of the array
     */
    static NewMultiArrayInstruction of(ClassEntry arrayTypeEntry,
                                       int dimensions) {
        return new AbstractInstruction.UnboundNewMultidimensionalArrayInstruction(arrayTypeEntry, dimensions);
    }
}
