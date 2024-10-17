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
import jdk.internal.classfile.impl.BytecodeHelpers;
import jdk.internal.classfile.impl.Util;

/**
 * Models a return-from-method instruction in the {@code code} array of a
 * {@code Code} attribute.  Corresponding opcodes will have a {@code kind} of
 * {@link Opcode.Kind#RETURN}.  Delivered as a {@link CodeElement} when
 * traversing the elements of a {@link CodeModel}.
 */
public sealed interface ReturnInstruction extends Instruction
        permits AbstractInstruction.UnboundReturnInstruction {
    TypeKind typeKind();

    /**
     * {@return a return instruction}
     *
     * @param typeKind the type of the return instruction
     */
    static ReturnInstruction of(TypeKind typeKind) {
        return of(BytecodeHelpers.returnOpcode(typeKind));
    }

    /**
     * {@return a return instruction}
     *
     * @param op the opcode for the specific type of return instruction,
     *           which must be of kind {@link Opcode.Kind#RETURN}
     */
    static ReturnInstruction of(Opcode op) {
        Util.checkKind(op, Opcode.Kind.RETURN);
        return new AbstractInstruction.UnboundReturnInstruction(op);
    }
}
