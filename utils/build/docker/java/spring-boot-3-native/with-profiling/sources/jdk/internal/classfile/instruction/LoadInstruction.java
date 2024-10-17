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
 * Models a local variable load instruction in the {@code code} array of a
 * {@code Code} attribute.  Corresponding opcodes will have a {@code kind} of
 * {@link Opcode.Kind#LOAD}.  Delivered as a {@link CodeElement} when
 * traversing the elements of a {@link CodeModel}.
 */
public sealed interface LoadInstruction extends Instruction
        permits AbstractInstruction.BoundLoadInstruction,
                AbstractInstruction.UnboundLoadInstruction {
    int slot();

    TypeKind typeKind();

    /**
     * {@return a local variable load instruction}
     *
     * @param kind the type of the value to be loaded
     * @param slot the local varaible slot to load from
     */
    static LoadInstruction of(TypeKind kind, int slot) {
        return of(BytecodeHelpers.loadOpcode(kind, slot), slot);
    }

    /**
     * {@return a local variable load instruction}
     *
     * @param op the opcode for the specific type of load instruction,
     *           which must be of kind {@link Opcode.Kind#LOAD}
     * @param slot the local varaible slot to load from
     */
    static LoadInstruction of(Opcode op, int slot) {
        Util.checkKind(op, Opcode.Kind.LOAD);
        return new AbstractInstruction.UnboundLoadInstruction(op, slot);
    }
}
