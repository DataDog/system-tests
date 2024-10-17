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
 * Models a {@code new} instruction in the {@code code} array of a {@code Code}
 * attribute.  Delivered as a {@link CodeElement} when traversing the elements
 * of a {@link CodeModel}.
 */
public sealed interface NewObjectInstruction extends Instruction
        permits AbstractInstruction.BoundNewObjectInstruction, AbstractInstruction.UnboundNewObjectInstruction {

    /**
     * {@return the type of object to create}
     */
    ClassEntry className();

    /**
     * {@return a new object instruction}
     *
     * @param className the type of object to create
     */
    static NewObjectInstruction of(ClassEntry className) {
        return new AbstractInstruction.UnboundNewObjectInstruction(className);
    }
}
