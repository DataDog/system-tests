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
import jdk.internal.classfile.Label;
import jdk.internal.classfile.Opcode;
import jdk.internal.classfile.impl.AbstractInstruction;
import jdk.internal.classfile.impl.Util;

/**
 * Models a branching instruction (conditional or unconditional) in the {@code
 * code} array of a {@code Code} attribute.  Corresponding opcodes will have a
 * {@code kind} of {@link Opcode.Kind#BRANCH}.  Delivered as a {@link
 * CodeElement} when traversing the elements of a {@link CodeModel}.
 */
public sealed interface BranchInstruction extends Instruction
        permits AbstractInstruction.BoundBranchInstruction,
                AbstractInstruction.UnboundBranchInstruction {
    /**
     * {@return the target of the branch}
     */
    Label target();

    /**
     * {@return a branch instruction}
     *
     * @param op the opcode for the specific type of branch instruction,
     *           which must be of kind {@link Opcode.Kind#BRANCH}
     */
    static BranchInstruction of(Opcode op, Label target) {
        Util.checkKind(op, Opcode.Kind.BRANCH);
        return new AbstractInstruction.UnboundBranchInstruction(op, target);
    }
}
