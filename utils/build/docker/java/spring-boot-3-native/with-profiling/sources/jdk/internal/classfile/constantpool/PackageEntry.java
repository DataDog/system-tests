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
import java.lang.constant.PackageDesc;

/**
 * Models a {@code CONSTANT_Package_info} constant in the constant pool of a
 * classfile.
 */
public sealed interface PackageEntry extends PoolEntry
        permits AbstractPoolEntry.PackageEntryImpl {
    /**
     * {@return the package name}
     */
    Utf8Entry name();

    /**
     * {@return a symbolic descriptor for the package name}
     */
    PackageDesc asSymbol();
}
