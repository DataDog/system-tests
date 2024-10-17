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

import java.lang.constant.ClassDesc;

import jdk.internal.classfile.CodeElement;
import jdk.internal.classfile.CodeModel;
import jdk.internal.classfile.constantpool.ClassEntry;
import jdk.internal.classfile.Instruction;
import jdk.internal.classfile.Opcode;
import jdk.internal.classfile.impl.AbstractInstruction;
import jdk.internal.classfile.impl.TemporaryConstantPool;
import jdk.internal.classfile.impl.Util;

/**
 * Models an {@code instanceof} or {@code checkcast} instruction in the {@code
 * code} array of a {@code Code} attribute.  Delivered as a {@link CodeElement}
 * when traversing the elements of a {@link CodeModel}.
 */
public sealed interface TypeCheckInstruction extends Instruction
        permits AbstractInstruction.BoundTypeCheckInstruction,
                AbstractInstruction.UnboundTypeCheckInstruction {
    ClassEntry type();

    /**
     * {@return a type check instruction}
     *
     * @param op the opcode for the specific type of type check instruction,
     *           which must be of kind {@link Opcode.Kind#TYPE_CHECK}
     * @param type the type against which to check or cast
     */
    static TypeCheckInstruction of(Opcode op, ClassEntry type) {
        Util.checkKind(op, Opcode.Kind.TYPE_CHECK);
        return new AbstractInstruction.UnboundTypeCheckInstruction(op, type);
    }

    /**
     * {@return a type check instruction}
     *
     * @param op the opcode for the specific type of type check instruction,
     *           which must be of kind {@link Opcode.Kind#TYPE_CHECK}
     * @param type the type against which to check or cast
     */
    static TypeCheckInstruction of(Opcode op, ClassDesc type) {
        return of(op, TemporaryConstantPool.INSTANCE.classEntry(type));
    }
}
