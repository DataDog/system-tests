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

import jdk.internal.classfile.attribute.RuntimeInvisibleTypeAnnotationsAttribute;
import jdk.internal.classfile.attribute.RuntimeVisibleTypeAnnotationsAttribute;
import jdk.internal.classfile.attribute.StackMapTableAttribute;

/**
 * A {@link ClassfileElement} that can appear when traversing the elements
 * of a {@link CodeModel} or be presented to a {@link CodeBuilder}.  Code elements
 * are either an {@link Instruction}, which models an instruction in the body
 * of a method, or a {@link PseudoInstruction}, which models metadata from
 * the code attribute, such as line number metadata, local variable metadata,
 * exception metadata, label target metadata, etc.
 */
public sealed interface CodeElement extends ClassfileElement
        permits Instruction, PseudoInstruction,
                CustomAttribute, RuntimeVisibleTypeAnnotationsAttribute, RuntimeInvisibleTypeAnnotationsAttribute,
                StackMapTableAttribute {
}
