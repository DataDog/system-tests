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
import jdk.internal.classfile.Label;
import jdk.internal.classfile.PseudoInstruction;
import jdk.internal.classfile.impl.LabelImpl;

/**
 * A pseudo-instruction which indicates that the specified label corresponds to
 * the current position in the {@code Code} attribute.  Delivered as a {@link
 * CodeElement} during traversal of the elements of a {@link CodeModel}.
 *
 * @see PseudoInstruction
 */
public sealed interface LabelTarget extends PseudoInstruction
        permits LabelImpl {
    Label label();
}
