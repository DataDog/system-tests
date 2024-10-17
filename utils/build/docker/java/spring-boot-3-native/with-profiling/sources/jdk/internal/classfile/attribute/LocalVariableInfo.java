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

import java.lang.constant.ClassDesc;
import jdk.internal.classfile.constantpool.Utf8Entry;
import jdk.internal.classfile.impl.BoundLocalVariable;
import jdk.internal.classfile.impl.UnboundAttribute;

/**
 * Models a single local variable in the {@link LocalVariableTableAttribute}.
 */
public sealed interface LocalVariableInfo
        permits UnboundAttribute.UnboundLocalVariableInfo, BoundLocalVariable {

    /**
     * {@return the index into the code array (inclusive) at which the scope of
     * this variable begins}
     */
    int startPc();

    /**
     * {@return the length of the region of the code array in which this
     * variable is in scope.}
     */
    int length();

    /**
     * {@return the name of the local variable}
     */
    Utf8Entry name();

    /**
     * {@return the field descriptor of the local variable}
     */
    Utf8Entry type();

    /**
     * {@return the field descriptor of the local variable}
     */
    default ClassDesc typeSymbol() {
        return ClassDesc.ofDescriptor(type().stringValue());
    }

    /**
     * {@return the index into the local variable array of the current frame
     * which holds this local variable}
     */
    int slot();
}
