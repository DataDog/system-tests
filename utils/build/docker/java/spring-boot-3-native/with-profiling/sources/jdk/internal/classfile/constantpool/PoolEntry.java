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

import jdk.internal.classfile.WritableElement;

/**
 * Models an entry in the constant pool of a classfile.
 */
public sealed interface PoolEntry extends WritableElement<PoolEntry>
        permits AnnotationConstantValueEntry, DynamicConstantPoolEntry,
                LoadableConstantEntry, MemberRefEntry, ModuleEntry, NameAndTypeEntry,
                PackageEntry {

    /**
     * {@return the constant pool this entry is from}
     */
    ConstantPool constantPool();

    /**
     * {@return the constant pool tag that describes the type of this entry}
     */
    byte tag();

    /**
     * {@return the index within the constant pool corresponding to this entry}
     */
    int index();

    /**
     * {@return the number of constant pool slots this entry consumes}
     */
    int width();
}
