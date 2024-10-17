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

import jdk.internal.classfile.Attribute;
import jdk.internal.classfile.AttributeMapper;
import jdk.internal.classfile.BufWriter;

import static jdk.internal.classfile.Classfile.JAVA_1_VERSION;

public abstract class AbstractAttributeMapper<T extends Attribute<T>>
        implements AttributeMapper<T> {

    private final String name;
    private final boolean allowMultiple;
    private final int majorVersion;

    protected abstract void writeBody(BufWriter buf, T attr);

    public AbstractAttributeMapper(String name) {
        this(name, false);
    }

    public AbstractAttributeMapper(String name,
                                   boolean allowMultiple) {
        this(name, allowMultiple, JAVA_1_VERSION);
    }

    public AbstractAttributeMapper(String name,
                                   int majorVersion) {
        this(name, false, majorVersion);
    }

    public AbstractAttributeMapper(String name,
                                   boolean allowMultiple,
                                   int majorVersion) {
        this.name = name;
        this.allowMultiple = allowMultiple;
        this.majorVersion = majorVersion;
    }

    @Override
    public String name() {
        return name;
    }

    @Override
    public void writeAttribute(BufWriter buf, T attr) {
        buf.writeIndex(buf.constantPool().utf8Entry(name));
        buf.writeInt(0);
        int start = buf.size();
        writeBody(buf, attr);
        int written = buf.size() - start;
        buf.patchInt(start - 4, 4, written);
    }

    @Override
    public boolean allowMultiple() {
        return allowMultiple;
    }

    @Override
    public int validSince() {
        return majorVersion;
    }

    @Override
    public String toString() {
        return String.format("AttributeMapper[name=%s, allowMultiple=%b, validSince=%d]",
                name, allowMultiple, majorVersion);
    }
}
