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

import java.util.Optional;

import jdk.internal.classfile.Attribute;

public class AbstractDirectBuilder<M> {
    protected final SplitConstantPool constantPool;
    protected final AttributeHolder attributes = new AttributeHolder();
    protected M original;

    public AbstractDirectBuilder(SplitConstantPool constantPool) {
        this.constantPool = constantPool;
    }

    public SplitConstantPool constantPool() {
        return constantPool;
    }

    public Optional<M> original() {
        return Optional.ofNullable(original);
    }

    public void setOriginal(M original) {
        this.original = original;
    }

    public void writeAttribute(Attribute<?> a) {
        attributes.withAttribute(a);
    }
}
