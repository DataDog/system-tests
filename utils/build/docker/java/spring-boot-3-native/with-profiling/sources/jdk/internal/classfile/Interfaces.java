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

import java.lang.constant.ClassDesc;
import java.util.Arrays;
import java.util.List;

import jdk.internal.classfile.constantpool.ClassEntry;
import jdk.internal.classfile.impl.InterfacesImpl;
import jdk.internal.classfile.impl.Util;

/**
 * Models the interfaces of a class.  Delivered as a {@link
 * jdk.internal.classfile.ClassElement} when traversing a {@link ClassModel}.
 */
public sealed interface Interfaces
        extends ClassElement
        permits InterfacesImpl {

    /** {@return the interfaces of this class} */
    List<ClassEntry> interfaces();

    /**
     * {@return an {@linkplain Interfaces} element}
     * @param interfaces the interfaces
     */
    static Interfaces of(List<ClassEntry> interfaces) {
        return new InterfacesImpl(interfaces);
    }

    /**
     * {@return an {@linkplain Interfaces} element}
     * @param interfaces the interfaces
     */
    static Interfaces of(ClassEntry... interfaces) {
        return of(List.of(interfaces));
    }

    /**
     * {@return an {@linkplain Interfaces} element}
     * @param interfaces the interfaces
     */
    static Interfaces ofSymbols(List<ClassDesc> interfaces) {
        return of(Util.entryList(interfaces));
    }

    /**
     * {@return an {@linkplain Interfaces} element}
     * @param interfaces the interfaces
     */
    static Interfaces ofSymbols(ClassDesc... interfaces) {
        return ofSymbols(Arrays.asList(interfaces));
    }
}
