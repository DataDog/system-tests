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

package jdk.internal.classfile;

import jdk.internal.classfile.impl.AbstractInstruction;
import jdk.internal.classfile.instruction.ArrayLoadInstruction;
import jdk.internal.classfile.instruction.ArrayStoreInstruction;
import jdk.internal.classfile.instruction.BranchInstruction;
import jdk.internal.classfile.instruction.ConstantInstruction;
import jdk.internal.classfile.instruction.ConvertInstruction;
import jdk.internal.classfile.instruction.DiscontinuedInstruction;
import jdk.internal.classfile.instruction.FieldInstruction;
import jdk.internal.classfile.instruction.IncrementInstruction;
import jdk.internal.classfile.instruction.InvokeDynamicInstruction;
import jdk.internal.classfile.instruction.InvokeInstruction;
import jdk.internal.classfile.instruction.LoadInstruction;
import jdk.internal.classfile.instruction.LookupSwitchInstruction;
import jdk.internal.classfile.instruction.MonitorInstruction;
import jdk.internal.classfile.instruction.NewMultiArrayInstruction;
import jdk.internal.classfile.instruction.NewObjectInstruction;
import jdk.internal.classfile.instruction.NewPrimitiveArrayInstruction;
import jdk.internal.classfile.instruction.NewReferenceArrayInstruction;
import jdk.internal.classfile.instruction.NopInstruction;
import jdk.internal.classfile.instruction.OperatorInstruction;
import jdk.internal.classfile.instruction.ReturnInstruction;
import jdk.internal.classfile.instruction.StackInstruction;
import jdk.internal.classfile.instruction.StoreInstruction;
import jdk.internal.classfile.instruction.TableSwitchInstruction;
import jdk.internal.classfile.instruction.ThrowInstruction;
import jdk.internal.classfile.instruction.TypeCheckInstruction;

/**
 * Models an executable instruction in a method body.
 */
public sealed interface Instruction extends CodeElement
        permits ArrayLoadInstruction, ArrayStoreInstruction, BranchInstruction,
                ConstantInstruction, ConvertInstruction, DiscontinuedInstruction,
                FieldInstruction, InvokeDynamicInstruction, InvokeInstruction,
                LoadInstruction, StoreInstruction, IncrementInstruction,
                LookupSwitchInstruction, MonitorInstruction, NewMultiArrayInstruction,
                NewObjectInstruction, NewPrimitiveArrayInstruction, NewReferenceArrayInstruction,
                NopInstruction, OperatorInstruction, ReturnInstruction,
                StackInstruction, TableSwitchInstruction,
                ThrowInstruction, TypeCheckInstruction, AbstractInstruction {

    /**
     * {@return the opcode of this instruction}
     */
    Opcode opcode();

    /**
     * {@return the size in bytes of this instruction}
     */
    int sizeInBytes();
}
