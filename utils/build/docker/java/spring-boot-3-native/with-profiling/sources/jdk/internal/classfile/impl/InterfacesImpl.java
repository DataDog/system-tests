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

import java.util.List;
import java.util.stream.Collectors;

import jdk.internal.classfile.constantpool.ClassEntry;
import jdk.internal.classfile.Interfaces;

public final class InterfacesImpl
        extends AbstractElement
        implements Interfaces {
    private final List<ClassEntry> interfaces;

    public InterfacesImpl(List<ClassEntry> interfaces) {
        this.interfaces = List.copyOf(interfaces);
    }

    @Override
    public List<ClassEntry> interfaces() {
        return interfaces;
    }

    @Override
    public void writeTo(DirectClassBuilder builder) {
        builder.setInterfaces(interfaces);
    }

    @Override
    public String toString() {
        return String.format("Interfaces[interfaces=%s]", interfaces.stream()
                .map(iface -> iface.name().stringValue())
                .collect(Collectors.joining(", ")));
    }
}
