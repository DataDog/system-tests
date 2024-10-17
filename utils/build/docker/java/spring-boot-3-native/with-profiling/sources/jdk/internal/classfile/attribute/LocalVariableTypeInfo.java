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

import jdk.internal.classfile.constantpool.Utf8Entry;
import jdk.internal.classfile.impl.BoundLocalVariableType;
import jdk.internal.classfile.impl.UnboundAttribute;

/**
 * Models a single local variable in the {@link LocalVariableTypeTableAttribute}.
 */
public sealed interface LocalVariableTypeInfo
        permits UnboundAttribute.UnboundLocalVariableTypeInfo, BoundLocalVariableType {

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
     * {@return the field signature of the local variable}
     */
    Utf8Entry signature();

    /**
     * {@return the index into the local variable array of the current frame
     * which holds this local variable}
     */
    int slot();
}
