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

package jdk.internal.classfile.attribute;

import jdk.internal.classfile.Attribute;
import jdk.internal.classfile.impl.BoundAttribute;
import jdk.internal.classfile.impl.UnboundAttribute;

import java.util.List;

/**
 * Models the {@code LocalVariableTypeTable} attribute {@jvms 4.7.14}, which can appear
 * on a {@code Code} attribute, and records debug information about local
 * variables.
 * Delivered as a {@link jdk.internal.classfile.instruction.LocalVariable} when traversing the
 * elements of a {@link jdk.internal.classfile.CodeModel}, according to the setting of the
 * {@link jdk.internal.classfile.Classfile.Option#processLineNumbers(boolean)} option.
 */
public sealed interface LocalVariableTypeTableAttribute
        extends Attribute<LocalVariableTypeTableAttribute>
        permits BoundAttribute.BoundLocalVariableTypeTableAttribute, UnboundAttribute.UnboundLocalVariableTypeTableAttribute {

    /**
     * {@return debug information for the local variables in this method}
     */
    List<LocalVariableTypeInfo> localVariableTypes();

    /**
     * {@return a {@code LocalVariableTypeTable} attribute}
     * @param locals the local variable descriptions
     */
    static LocalVariableTypeTableAttribute of(List<LocalVariableTypeInfo> locals) {
        return new UnboundAttribute.UnboundLocalVariableTypeTableAttribute(locals);
    }
}
