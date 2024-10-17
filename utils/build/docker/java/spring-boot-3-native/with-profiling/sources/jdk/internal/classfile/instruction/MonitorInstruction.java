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
 * Models a {@code monitorenter} or {@code monitorexit} instruction in the
 * {@code code} array of a {@code Code} attribute.  Delivered as a {@link
 * CodeElement} when traversing the elements of a {@link CodeModel}.
 */
public sealed interface MonitorInstruction extends Instruction
        permits AbstractInstruction.UnboundMonitorInstruction {

    /**
     * {@return a monitor instruction}
     *
     * @param op the opcode for the specific type of monitor instruction,
     *           which must be of kind {@link Opcode.Kind#MONITOR}
     */
    static MonitorInstruction of(Opcode op) {
        Util.checkKind(op, Opcode.Kind.MONITOR);
        return new AbstractInstruction.UnboundMonitorInstruction(op);
    }
}
