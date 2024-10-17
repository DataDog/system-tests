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
 * Models a member reference constant in the constant pool of a classfile,
 * which includes references to fields, methods, and interface methods.
 */
public sealed interface MemberRefEntry extends PoolEntry
        permits FieldRefEntry, InterfaceMethodRefEntry, MethodRefEntry, AbstractPoolEntry.AbstractMemberRefEntry {
    /**
     * {@return the class in which this member ref lives}
     */
    ClassEntry owner();

    /**
     * {@return the name and type of the member}
     */
    NameAndTypeEntry nameAndType();

    /**
     * {@return the name of the member}
     */
    default Utf8Entry name() {
        return nameAndType().name();
    }

    /**
     * {@return the type of the member}
     */
    default Utf8Entry type() {
        return nameAndType().type();
    }
}
