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

import jdk.internal.classfile.BufWriter;
import jdk.internal.classfile.Classfile;
import jdk.internal.classfile.CodeElement;
import jdk.internal.classfile.CodeModel;
import jdk.internal.classfile.Label;
import jdk.internal.classfile.PseudoInstruction;
import jdk.internal.classfile.Signature;
import jdk.internal.classfile.attribute.LocalVariableTypeTableAttribute;
import jdk.internal.classfile.constantpool.Utf8Entry;
import jdk.internal.classfile.impl.AbstractPseudoInstruction;
import jdk.internal.classfile.impl.BoundLocalVariableType;
import jdk.internal.classfile.impl.TemporaryConstantPool;

/**
 * A pseudo-instruction which models a single entry in the {@link
 * LocalVariableTypeTableAttribute}.  Delivered as a {@link CodeElement} during
 * traversal of the elements of a {@link CodeModel}, according to the setting of
 * the {@link Classfile.Option#processDebug(boolean)} option.
 */
public sealed interface LocalVariableType extends PseudoInstruction
        permits AbstractPseudoInstruction.UnboundLocalVariableType, BoundLocalVariableType {
    /**
     * {@return the local variable slot}
     */
    int slot();

    /**
     * {@return the local variable name}
     */
    Utf8Entry name();

    /**
     * {@return the local variable signature}
     */
    Utf8Entry signature();

    /**
     * {@return the local variable signature}
     */
    default Signature signatureSymbol() {
        return Signature.parseFrom(signature().stringValue());
    }

    /**
     * {@return the start range of the local variable scope}
     */
    Label startScope();

    /**
     * {@return the end range of the local variable scope}
     */
    Label endScope();

    boolean writeTo(BufWriter buf);

    /**
     * {@return a local variable type pseudo-instruction}
     *
     * @param slot the local variable slot
     * @param nameEntry the local variable name
     * @param signatureEntry the local variable signature
     * @param startScope the start range of the local variable scope
     * @param endScope the end range of the local variable scope
     */
    static LocalVariableType of(int slot, Utf8Entry nameEntry, Utf8Entry signatureEntry, Label startScope, Label endScope) {
        return new AbstractPseudoInstruction.UnboundLocalVariableType(slot, nameEntry, signatureEntry,
                                                                      startScope, endScope);
    }

    /**
     * {@return a local variable type pseudo-instruction}
     *
     * @param slot the local variable slot
     * @param name the local variable name
     * @param signature the local variable signature
     * @param startScope the start range of the local variable scope
     * @param endScope the end range of the local variable scope
     */
    static LocalVariableType of(int slot, String name, Signature signature, Label startScope, Label endScope) {
        return of(slot,
                  TemporaryConstantPool.INSTANCE.utf8Entry(name),
                  TemporaryConstantPool.INSTANCE.utf8Entry(signature.signatureString()),
                  startScope, endScope);
    }
}
