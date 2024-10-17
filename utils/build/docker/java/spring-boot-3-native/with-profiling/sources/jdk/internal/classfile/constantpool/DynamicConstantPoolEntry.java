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

import jdk.internal.classfile.BootstrapMethodEntry;

/**
 * Models a dynamic constant pool entry, which is either {@link ConstantDynamicEntry}
 * or {@link InvokeDynamicEntry}.
 */
public sealed interface DynamicConstantPoolEntry extends PoolEntry
        permits ConstantDynamicEntry, InvokeDynamicEntry {

    /**
     * {@return the entry in the bootstrap method table for this constant}
     */
    BootstrapMethodEntry bootstrap();

    /**
     * {@return the invocation name and type}
     */
    NameAndTypeEntry nameAndType();

    /**
     * {@return the invocation name}
     */
    default Utf8Entry name() {
        return nameAndType().name();
    }

    /**
     * {@return the invocation type}
     */
    default Utf8Entry type() {
        return nameAndType().type();
    }
}
