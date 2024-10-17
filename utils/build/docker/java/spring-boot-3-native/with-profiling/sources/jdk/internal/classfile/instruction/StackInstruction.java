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
import jdk.internal.classfile.impl.AbstractInstruction;
import jdk.internal.classfile.impl.Util;

/**
 * Models a stack manipulation instruction in the {@code code} array of a
 * {@code Code} attribute.  Corresponding opcodes will have a {@code kind} of
 * {@link Opcode.Kind#STACK}.  Delivered as a {@link CodeElement} when
 * traversing the elements of a {@link CodeModel}.
 */
public sealed interface StackInstruction extends Instruction
        permits AbstractInstruction.UnboundStackInstruction {

    /**
     * {@return a stack manipulation instruction}
     *
     * @param op the opcode for the specific type of stack instruction,
     *           which must be of kind {@link Opcode.Kind#STACK}
     */
    static StackInstruction of(Opcode op) {
        Util.checkKind(op, Opcode.Kind.STACK);
        return new AbstractInstruction.UnboundStackInstruction(op);
    }
}
