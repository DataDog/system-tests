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

import java.lang.constant.ConstantDesc;

import jdk.internal.classfile.CodeElement;
import jdk.internal.classfile.CodeModel;
import jdk.internal.classfile.Instruction;
import jdk.internal.classfile.Opcode;
import jdk.internal.classfile.TypeKind;
import jdk.internal.classfile.constantpool.LoadableConstantEntry;
import jdk.internal.classfile.impl.AbstractInstruction;
import jdk.internal.classfile.impl.Util;

/**
 * Models a constant-load instruction in the {@code code} array of a {@code
 * Code} attribute, including "intrinsic constant" instructions (e.g., {@code
 * iconst_0}), "argument constant" instructions (e.g., {@code bipush}), and "load
 * constant" instructions (e.g., {@code LDC}).  Corresponding opcodes will have
 * a {@code kind} of {@link Opcode.Kind#CONSTANT}.  Delivered as a {@link
 * CodeElement} when traversing the elements of a {@link CodeModel}.
 */
public sealed interface ConstantInstruction extends Instruction {

    /**
     * {@return the constant value}
     */
    ConstantDesc constantValue();

    /**
     * {@return the type of the constant}
     */
    TypeKind typeKind();

    /**
     * Models an "intrinsic constant" instruction (e.g., {@code
     * iconst_0}).
     */
    sealed interface IntrinsicConstantInstruction extends ConstantInstruction
            permits AbstractInstruction.UnboundIntrinsicConstantInstruction {

        /**
         * {@return the type of the constant}
         */
        @Override
        default TypeKind typeKind() {
            return opcode().primaryTypeKind();
        }
    }

    /**
     * Models an "argument constant" instruction (e.g., {@code
     * bipush}).
     */
    sealed interface ArgumentConstantInstruction extends ConstantInstruction
            permits AbstractInstruction.BoundArgumentConstantInstruction,
                    AbstractInstruction.UnboundArgumentConstantInstruction {

        @Override
        Integer constantValue();

        /**
         * {@return the type of the constant}
         */
        @Override
        default TypeKind typeKind() {
            return opcode().primaryTypeKind();
        }
    }

    /**
     * Models a "load constant" instruction (e.g., {@code
     * ldc}).
     */
    sealed interface LoadConstantInstruction extends ConstantInstruction
            permits AbstractInstruction.BoundLoadConstantInstruction,
                    AbstractInstruction.UnboundLoadConstantInstruction {

        /**
         * {@return the constant value}
         */
        LoadableConstantEntry constantEntry();

        /**
         * {@return the type of the constant}
         */
        @Override
        default TypeKind typeKind() {
            return constantEntry().typeKind();
        }
    }

    /**
     * {@return an intrinsic constant instruction}
     *
     * @param op the opcode for the specific type of intrinsic constant instruction,
     *           which must be of kind {@link Opcode.Kind#CONSTANT}
     */
    static IntrinsicConstantInstruction ofIntrinsic(Opcode op) {
        Util.checkKind(op, Opcode.Kind.CONSTANT);
        if (op.constantValue() == null)
            throw new IllegalArgumentException(String.format("Wrong opcode specified; found %s, expected xCONST_val", op));
        return new AbstractInstruction.UnboundIntrinsicConstantInstruction(op);
    }

    /**
     * {@return an argument constant instruction}
     *
     * @param op the opcode for the specific type of intrinsic constant instruction,
     *           which must be of kind {@link Opcode.Kind#CONSTANT}
     * @param value the constant value
     */
    static ArgumentConstantInstruction ofArgument(Opcode op, int value) {
        Util.checkKind(op, Opcode.Kind.CONSTANT);
        if (op != Opcode.BIPUSH && op != Opcode.SIPUSH)
            throw new IllegalArgumentException(String.format("Wrong opcode specified; found %s, expected BIPUSH or SIPUSH", op, op.kind()));
        return new AbstractInstruction.UnboundArgumentConstantInstruction(op, value);
    }

    /**
     * {@return a load constant instruction}
     *
     * @param op the opcode for the specific type of load constant instruction,
     *           which must be of kind {@link Opcode.Kind#CONSTANT}
     * @param constant the constant value
     */
    static LoadConstantInstruction ofLoad(Opcode op, LoadableConstantEntry constant) {
        Util.checkKind(op, Opcode.Kind.CONSTANT);
        if (op != Opcode.LDC && op != Opcode.LDC_W && op != Opcode.LDC2_W)
            throw new IllegalArgumentException(String.format("Wrong opcode specified; found %s, expected LDC, LDC_W or LDC2_W", op, op.kind()));
        return new AbstractInstruction.UnboundLoadConstantInstruction(op, constant);
    }
}
