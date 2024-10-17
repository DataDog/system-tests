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
 * Models a local variable store instruction in the {@code code} array of a
 * {@code Code} attribute.  Corresponding opcodes will have a {@code kind} of
 * {@link Opcode.Kind#STORE}.  Delivered as a {@link CodeElement} when
 * traversing the elements of a {@link CodeModel}.
 */
public sealed interface StoreInstruction extends Instruction
        permits AbstractInstruction.BoundStoreInstruction, AbstractInstruction.UnboundStoreInstruction {
    int slot();
    TypeKind typeKind();

    /**
     * {@return a local variable store instruction}
     *
     * @param kind the type of the value to be stored
     * @param slot the local varaible slot to store to
     */
    static StoreInstruction of(TypeKind kind, int slot) {
        return of(BytecodeHelpers.storeOpcode(kind, slot), slot);
    }

    /**
     * {@return a local variable store instruction}
     *
     * @param op the opcode for the specific type of store instruction,
     *           which must be of kind {@link Opcode.Kind#STORE}
     * @param slot the local varaible slot to store to
     */
    static StoreInstruction of(Opcode op, int slot) {
        Util.checkKind(op, Opcode.Kind.STORE);
        return new AbstractInstruction.UnboundStoreInstruction(op, slot);
    }
}
