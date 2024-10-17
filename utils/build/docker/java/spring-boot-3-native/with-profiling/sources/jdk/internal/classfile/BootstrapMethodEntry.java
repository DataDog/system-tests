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

import java.util.List;

import jdk.internal.classfile.constantpool.ConstantPool;
import jdk.internal.classfile.constantpool.LoadableConstantEntry;
import jdk.internal.classfile.constantpool.MethodHandleEntry;
import jdk.internal.classfile.impl.BootstrapMethodEntryImpl;

/**
 * Models an entry in the bootstrap method table.  The bootstrap method table
 * is stored in the {@code BootstrapMethods} attribute, but is modeled by
 * the {@link ConstantPool}, since the bootstrap method table is logically
 * part of the constant pool.
 */
public sealed interface BootstrapMethodEntry
        extends WritableElement<BootstrapMethodEntry>
        permits BootstrapMethodEntryImpl {

    /**
     * {@return the constant pool associated with this entry}
     */
    ConstantPool constantPool();

    /**
     * {@return the index into the bootstrap method table corresponding to this entry}
     */
    int bsmIndex();

    /**
     * {@return the bootstrap method}
     */
    MethodHandleEntry bootstrapMethod();

    /**
     * {@return the bootstrap arguments}
     */
    List<LoadableConstantEntry> arguments();
}
