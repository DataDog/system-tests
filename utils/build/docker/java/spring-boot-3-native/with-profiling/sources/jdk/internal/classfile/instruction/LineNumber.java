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

import jdk.internal.classfile.Classfile;
import jdk.internal.classfile.CodeElement;
import jdk.internal.classfile.CodeModel;
import jdk.internal.classfile.PseudoInstruction;
import jdk.internal.classfile.attribute.LineNumberTableAttribute;
import jdk.internal.classfile.impl.LineNumberImpl;

/**
 * A pseudo-instruction which models a single entry in the
 * {@link LineNumberTableAttribute}.  Delivered as a {@link CodeElement}
 * during traversal of the elements of a {@link CodeModel}, according to
 * the setting of the {@link Classfile.Option#processLineNumbers(boolean)} option.
 *
 * @see PseudoInstruction
 */
public sealed interface LineNumber extends PseudoInstruction
        permits LineNumberImpl {

    /**
     * {@return the line number}
     */
    int line();

    /**
     * {@return a line number pseudo-instruction}
     *
     * @param line the line number
     */
    static LineNumber of(int line) {
        return LineNumberImpl.of(line);
    }
}
