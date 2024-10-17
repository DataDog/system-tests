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

public abstract class AbstractElement {
    public AbstractElement() { }

    public void writeTo(DirectCodeBuilder builder) {
        throw new UnsupportedOperationException();
    }

    public void writeTo(DirectClassBuilder builder) {
        throw new UnsupportedOperationException();
    }

    public void writeTo(DirectMethodBuilder builder) {
        throw new UnsupportedOperationException();
    }

    public void writeTo(DirectFieldBuilder builder) {
        throw new UnsupportedOperationException();
    }
}
