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

import jdk.internal.classfile.attribute.CodeAttribute;
import jdk.internal.classfile.instruction.CharacterRange;
import jdk.internal.classfile.instruction.ExceptionCatch;
import jdk.internal.classfile.instruction.LabelTarget;
import jdk.internal.classfile.instruction.LineNumber;
import jdk.internal.classfile.instruction.LocalVariable;
import jdk.internal.classfile.instruction.LocalVariableType;
import jdk.internal.classfile.impl.AbstractPseudoInstruction;

/**
 * Models metadata about a {@link CodeAttribute}, such as entries in the
 * exception table, line number table, local variable table, or the mapping
 * between instructions and labels.  Pseudo-instructions are delivered as part
 * of the element stream of a {@link CodeModel}.  Delivery of some
 * pseudo-instructions can be disabled by modifying the value of classfile
 * options (e.g., {@link Classfile.Option#processDebug(boolean)}).
 */
public sealed interface PseudoInstruction
        extends CodeElement
        permits CharacterRange, ExceptionCatch, LabelTarget, LineNumber, LocalVariable, LocalVariableType, AbstractPseudoInstruction {
}
