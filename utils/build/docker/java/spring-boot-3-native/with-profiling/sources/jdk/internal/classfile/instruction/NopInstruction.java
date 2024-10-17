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
import jdk.internal.classfile.impl.AbstractInstruction;

/**
 * Models a {@code nop} invocation instruction in the {@code code}
 * array of a {@code Code} attribute.  Delivered as a {@link CodeElement}
 * when traversing the elements of a {@link CodeModel}.
 */
public sealed interface NopInstruction extends Instruction
        permits AbstractInstruction.UnboundNopInstruction {
    /**
     * {@return a no-op instruction}
     */
    static NopInstruction of() {
        return new AbstractInstruction.UnboundNopInstruction();
    }
}
