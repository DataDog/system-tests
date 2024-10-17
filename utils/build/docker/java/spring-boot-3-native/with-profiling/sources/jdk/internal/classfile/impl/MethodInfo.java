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

import java.lang.constant.MethodTypeDesc;
import jdk.internal.classfile.constantpool.Utf8Entry;

import static jdk.internal.classfile.Classfile.ACC_STATIC;

public interface MethodInfo {
    Utf8Entry methodName();
    Utf8Entry methodType();
    MethodTypeDesc methodTypeSymbol();
    int methodFlags();

    default int receiverSlot() {
        if ((methodFlags() & ACC_STATIC) != 0)
            throw new IllegalStateException("not an instance method");
        return 0;
    }

    int parameterSlot(int paramNo);
}
