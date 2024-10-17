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
import jdk.internal.classfile.constantpool.FieldRefEntry;
import jdk.internal.classfile.constantpool.NameAndTypeEntry;
import jdk.internal.classfile.constantpool.Utf8Entry;
import jdk.internal.classfile.impl.AbstractInstruction;
import jdk.internal.classfile.impl.AbstractPoolEntry;
import jdk.internal.classfile.impl.TemporaryConstantPool;
import jdk.internal.classfile.impl.Util;

/**
 * Models a field access instruction in the {@code code} array of a {@code Code}
 * attribute.  Corresponding opcodes will have a {@code kind} of {@link
 * Opcode.Kind#FIELD_ACCESS}.  Delivered as a {@link CodeElement} when
 * traversing the elements of a {@link CodeModel}.
 */
public sealed interface FieldInstruction extends Instruction
        permits AbstractInstruction.BoundFieldInstruction, AbstractInstruction.UnboundFieldInstruction {
    /**
     * {@return the {@link FieldRefEntry} constant described by this instruction}
     */
    FieldRefEntry field();

    /**
     * {@return the class holding the field}
     */
    default ClassEntry owner() {
        return field().owner();
    }

    /**
     * {@return the name of the field}
     */
    default Utf8Entry name() {
        return field().nameAndType().name();
    }

    /**
     * {@return the field descriptor of the field}
     */
    default Utf8Entry type() {
        return field().nameAndType().type();
    }

    /**
     * {@return a symbolic descriptor for the type of the field}
     */
    default ClassDesc typeSymbol() {
        return Util.fieldTypeSymbol(field().nameAndType());
    }

    /**
     * {@return a field access instruction}
     *
     * @param op the opcode for the specific type of field access instruction,
     *           which must be of kind {@link Opcode.Kind#FIELD_ACCESS}
     * @param field a constant pool entry describing the field
     */
    static FieldInstruction of(Opcode op, FieldRefEntry field) {
        Util.checkKind(op, Opcode.Kind.FIELD_ACCESS);
        return new AbstractInstruction.UnboundFieldInstruction(op, field);
    }

    /**
     * {@return a field access instruction}
     *
     * @param op the opcode for the specific type of field access instruction,
     *           which must be of kind {@link Opcode.Kind#FIELD_ACCESS}
     * @param owner the class holding the field
     * @param name the name of the field
     * @param type the field descriptor
     */
    static FieldInstruction of(Opcode op,
                               ClassEntry owner,
                               Utf8Entry name,
                               Utf8Entry type) {
        return of(op, owner, TemporaryConstantPool.INSTANCE.nameAndTypeEntry(name, type));
    }

    /**
     * {@return a field access instruction}
     *
     * @param op the opcode for the specific type of field access instruction,
     *           which must be of kind {@link Opcode.Kind#FIELD_ACCESS}
     * @param owner the class holding the field
     * @param nameAndType the name and field descriptor of the field
     */
    static FieldInstruction of(Opcode op,
                               ClassEntry owner,
                               NameAndTypeEntry nameAndType) {
        return of(op, TemporaryConstantPool.INSTANCE.fieldRefEntry(owner, nameAndType));
    }
}
