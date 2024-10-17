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

import jdk.internal.classfile.constantpool.ConstantPool;
import jdk.internal.classfile.BootstrapMethodEntry;
import jdk.internal.classfile.BufWriter;
import jdk.internal.classfile.constantpool.LoadableConstantEntry;
import jdk.internal.classfile.constantpool.MethodHandleEntry;

import static jdk.internal.classfile.impl.AbstractPoolEntry.MethodHandleEntryImpl;

public final class BootstrapMethodEntryImpl implements BootstrapMethodEntry {

    final int index;
    final int hash;
    private final ConstantPool constantPool;
    private final MethodHandleEntryImpl handle;
    private final List<LoadableConstantEntry> arguments;

    BootstrapMethodEntryImpl(ConstantPool constantPool, int bsmIndex, int hash,
                                 MethodHandleEntryImpl handle,
                                 List<LoadableConstantEntry> arguments) {
        this.index = bsmIndex;
        this.hash = hash;
        this.constantPool = constantPool;
        this.handle = handle;
        this.arguments = List.copyOf(arguments);
    }

    @Override
    public ConstantPool constantPool() {
        return constantPool;
    }

    @Override
    public MethodHandleEntry bootstrapMethod() {
        return handle;
    }

    @Override
    public List<LoadableConstantEntry> arguments() {
        return arguments;
    }

    @Override
    public boolean equals(Object obj) {
        return obj instanceof BootstrapMethodEntry e
                && e.bootstrapMethod().equals(handle)
                && e.arguments().equals(arguments);
    }

    static int computeHashCode(MethodHandleEntryImpl handle,
                               List<? extends LoadableConstantEntry> arguments) {
        int hash = handle.hashCode();
        hash = 31 * hash + arguments.hashCode();
        return AbstractPoolEntry.phiMix(hash);
    }

    @Override
    public int bsmIndex() { return index; }

    @Override
    public int hashCode() {
        return hash;
    }

    @Override
    public void writeTo(BufWriter writer) {
        writer.writeIndex(bootstrapMethod());
        writer.writeListIndices(arguments());
    }
}
