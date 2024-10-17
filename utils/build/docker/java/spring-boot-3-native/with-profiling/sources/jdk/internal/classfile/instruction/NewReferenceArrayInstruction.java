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
 * Models a {@code anewarray} invocation instruction in the {@code code}
 * array of a {@code Code} attribute.  Delivered as a {@link CodeElement}
 * when traversing the elements of a {@link CodeModel}.
 */
public sealed interface NewReferenceArrayInstruction extends Instruction
        permits AbstractInstruction.BoundNewReferenceArrayInstruction, AbstractInstruction.UnboundNewReferenceArrayInstruction {
    /**
     * {@return the component type of the array}
     */
    ClassEntry componentType();

    /**
     * {@return a new reference array instruction}
     *
     * @param componentType the component type of the array
     */
    static NewReferenceArrayInstruction of(ClassEntry componentType) {
        return new AbstractInstruction.UnboundNewReferenceArrayInstruction(componentType);
    }
}
