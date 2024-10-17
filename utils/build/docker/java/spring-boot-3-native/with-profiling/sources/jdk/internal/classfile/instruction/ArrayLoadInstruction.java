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
import jdk.internal.classfile.Instruction;
import jdk.internal.classfile.Opcode;
import jdk.internal.classfile.TypeKind;
import jdk.internal.classfile.impl.AbstractInstruction;
import jdk.internal.classfile.impl.Util;

/**
 * Models an array load instruction in the {@code code} array of a {@code Code}
 * attribute.  Corresponding opcodes will have a {@code kind} of {@link
 * Opcode.Kind#ARRAY_LOAD}.  Delivered as a {@link CodeElement} when
 * traversing the elements of a {@link CodeModel}.
 */
public sealed interface ArrayLoadInstruction extends Instruction
        permits AbstractInstruction.UnboundArrayLoadInstruction {
    /**
     * {@return the component type of the array}
     */
    TypeKind typeKind();

    /**
     * {@return an array load instruction}
     *
     * @param op the opcode for the specific type of array load instruction,
     *           which must be of kind {@link Opcode.Kind#ARRAY_LOAD}
     */
    static ArrayLoadInstruction of(Opcode op) {
        Util.checkKind(op, Opcode.Kind.ARRAY_LOAD);
        return new AbstractInstruction.UnboundArrayLoadInstruction(op);
    }
}
