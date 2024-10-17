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
import jdk.internal.classfile.TypeKind;
import jdk.internal.classfile.impl.AbstractInstruction;

/**
 * Models a {@code newarray} invocation instruction in the {@code code}
 * array of a {@code Code} attribute.  Delivered as a {@link CodeElement}
 * when traversing the elements of a {@link CodeModel}.
 */
public sealed interface NewPrimitiveArrayInstruction extends Instruction
        permits AbstractInstruction.BoundNewPrimitiveArrayInstruction,
                AbstractInstruction.UnboundNewPrimitiveArrayInstruction {
    /**
     * {@return the component type of the array}
     */
    TypeKind typeKind();

    /**
     * {@return a new primitive array instruction}
     *
     * @param typeKind the component type of the array
     */
    static NewPrimitiveArrayInstruction of(TypeKind typeKind) {
        return new AbstractInstruction.UnboundNewPrimitiveArrayInstruction(typeKind);
    }
}
