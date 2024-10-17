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

import jdk.internal.classfile.Attribute;
import jdk.internal.classfile.ClassReader;
import jdk.internal.classfile.attribute.RecordComponentInfo;
import jdk.internal.classfile.constantpool.Utf8Entry;

public final class BoundRecordComponentInfo
        implements RecordComponentInfo {

    private final ClassReader reader;
    private final int startPos, attributesPos;
    private List<Attribute<?>> attributes;

    public BoundRecordComponentInfo(ClassReader reader, int startPos) {
        this.reader = reader;
        this.startPos = startPos;
        attributesPos = startPos + 4;
    }

    @Override
    public Utf8Entry name() {
        return reader.readUtf8Entry(startPos);
    }

    @Override
    public Utf8Entry descriptor() {
        return reader.readUtf8Entry(startPos + 2);
    }

    @Override
    public List<Attribute<?>> attributes() {
        if (attributes == null) {
            attributes = BoundAttribute.readAttributes(null, reader, attributesPos, reader.customAttributes());
        }
        return attributes;
    }
}
