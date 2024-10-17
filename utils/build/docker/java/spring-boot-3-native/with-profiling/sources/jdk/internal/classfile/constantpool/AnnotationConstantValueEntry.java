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
package jdk.internal.classfile.constantpool;

import java.lang.constant.ConstantDesc;

/**
 * A constant pool entry that may be used as an annotation constant,
 * which includes the four kinds of primitive constants, and UTF8 constants.
 */
public sealed interface AnnotationConstantValueEntry extends PoolEntry
        permits DoubleEntry, FloatEntry, IntegerEntry, LongEntry, Utf8Entry {

    /**
     * {@return the constant value}  The constant value will be an {@link Integer},
     * {@link Long}, {@link Float}, {@link Double}, or {@link String}.
     */
    ConstantDesc constantValue();
}
