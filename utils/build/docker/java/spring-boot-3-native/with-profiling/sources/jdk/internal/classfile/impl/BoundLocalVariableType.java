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
package jdk.internal.classfile.impl;

import jdk.internal.classfile.attribute.LocalVariableTypeInfo;
import jdk.internal.classfile.constantpool.Utf8Entry;
import jdk.internal.classfile.instruction.LocalVariableType;

public final class BoundLocalVariableType
        extends AbstractBoundLocalVariable
        implements LocalVariableTypeInfo,
                   LocalVariableType {

    public BoundLocalVariableType(CodeImpl code, int offset) {
        super(code, offset);
    }

    @Override
    public Utf8Entry signature() {
        return secondaryEntry();
    }

    @Override
    public void writeTo(DirectCodeBuilder writer) {
        writer.addLocalVariableType(this);
    }

    @Override
    public String toString() {
        return String.format("LocalVariableType[name=%s, slot=%d, signature=%s]", name().stringValue(), slot(), signature().stringValue());
    }
}
