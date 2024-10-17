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
 * Models an array store instruction in the {@code code} array of a {@code Code}
 * attribute.  Corresponding opcodes will have a {@code kind} of {@link
 * Opcode.Kind#ARRAY_STORE}.  Delivered as a {@link CodeElement} when
 * traversing the elements of a {@link CodeModel}.
 */
public sealed interface ArrayStoreInstruction extends Instruction
        permits AbstractInstruction.UnboundArrayStoreInstruction {
    /**
     * {@return the component type of the array}
     */
    TypeKind typeKind();

    /**
     * {@return an array store instruction}
     *
     * @param op the opcode for the specific type of array store instruction,
     *           which must be of kind {@link Opcode.Kind#ARRAY_STORE}
     */
    static ArrayStoreInstruction of(Opcode op) {
        Util.checkKind(op, Opcode.Kind.ARRAY_STORE);
        return new AbstractInstruction.UnboundArrayStoreInstruction(op);
    }
}
