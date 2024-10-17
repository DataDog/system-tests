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

import java.util.List;

import jdk.internal.classfile.CodeElement;
import jdk.internal.classfile.CodeModel;
import jdk.internal.classfile.Instruction;
import jdk.internal.classfile.Label;
import jdk.internal.classfile.impl.AbstractInstruction;

/**
 * Models a {@code lookupswitch} instruction in the {@code code} array of a
 * {@code Code} attribute.  Delivered as a {@link CodeElement} when traversing
 * the elements of a {@link CodeModel}.
 */
public sealed interface LookupSwitchInstruction extends Instruction
        permits AbstractInstruction.BoundLookupSwitchInstruction,
                AbstractInstruction.UnboundLookupSwitchInstruction {
    /**
     * {@return the target of the default case}
     */
    Label defaultTarget();

    /**
     * {@return the cases of the switch}
     */
    List<SwitchCase> cases();

    /**
     * {@return a lookup switch instruction}
     *
     * @param defaultTarget the default target of the switch
     * @param cases the cases of the switch
     */
    static LookupSwitchInstruction of(Label defaultTarget, List<SwitchCase> cases) {
        return new AbstractInstruction.UnboundLookupSwitchInstruction(defaultTarget, cases);
    }
}
