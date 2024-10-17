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

import java.util.Optional;

import jdk.internal.classfile.CodeElement;
import jdk.internal.classfile.CodeModel;
import jdk.internal.classfile.constantpool.ClassEntry;
import jdk.internal.classfile.Label;
import jdk.internal.classfile.PseudoInstruction;
import jdk.internal.classfile.impl.AbstractPseudoInstruction;

/**
 * A pseudo-instruction modeling an entry in the exception table of a code
 * attribute.  Entries in the exception table model catch and finally blocks.
 * Delivered as a {@link CodeElement} when traversing the contents
 * of a {@link CodeModel}.
 *
 * @see PseudoInstruction
 */
public sealed interface ExceptionCatch extends PseudoInstruction
        permits AbstractPseudoInstruction.ExceptionCatchImpl {
    /**
     * {@return the handler for the exception}
     */
    Label handler();

    /**
     * {@return the beginning of the instruction range for the guarded instructions}
     */
    Label tryStart();

    /**
     * {@return the end of the instruction range for the guarded instructions}
     */
    Label tryEnd();

    /**
     * {@return the type of the exception to catch, or empty if this handler is
     * unconditional}
     */
    Optional<ClassEntry> catchType();

    /**
     * {@return an exception table pseudo-instruction}
     * @param handler the handler for the exception
     * @param tryStart the beginning of the instruction range for the gaurded instructions
     * @param tryEnd the end of the instruction range for the gaurded instructions
     * @param catchTypeEntry the type of exception to catch, or empty if this
     *                       handler is unconditional
     */
    static ExceptionCatch of(Label handler, Label tryStart, Label tryEnd,
                             Optional<ClassEntry> catchTypeEntry) {
        return new AbstractPseudoInstruction.ExceptionCatchImpl(handler, tryStart, tryEnd, catchTypeEntry.orElse(null));
    }

    /**
     * {@return an exception table pseudo-instruction for an unconditional handler}
     * @param handler the handler for the exception
     * @param tryStart the beginning of the instruction range for the gaurded instructions
     * @param tryEnd the end of the instruction range for the gaurded instructions
     */
    static ExceptionCatch of(Label handler, Label tryStart, Label tryEnd) {
        return new AbstractPseudoInstruction.ExceptionCatchImpl(handler, tryStart, tryEnd, (ClassEntry) null);
    }
}
