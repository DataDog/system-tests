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

import jdk.internal.classfile.impl.AbstractPoolEntry;

/**
 * Models a {@code CONSTANT_NameAndType_info} constant in the constant pool of a
 * classfile.
 */
public sealed interface NameAndTypeEntry extends PoolEntry
        permits AbstractPoolEntry.NameAndTypeEntryImpl {

    /**
     * {@return the field or method name}
     */
    Utf8Entry name();

    /**
     * {@return the field or method descriptor}
     */
    Utf8Entry type();
}
