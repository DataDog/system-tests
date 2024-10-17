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
import java.lang.constant.ModuleDesc;

/**
 * Models a {@code CONSTANT_Module_info} constant in the constant pool of a
 * classfile.
 */
public sealed interface ModuleEntry extends PoolEntry
        permits AbstractPoolEntry.ModuleEntryImpl {
    /**
     * {@return the name of the module}
     */
    Utf8Entry name();

    /**
     * {@return a symbolic descriptor for the module}
     */
    ModuleDesc asSymbol();
}
