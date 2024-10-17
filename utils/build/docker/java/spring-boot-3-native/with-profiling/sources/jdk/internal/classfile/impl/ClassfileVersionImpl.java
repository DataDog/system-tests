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

import jdk.internal.classfile.ClassfileVersion;

public final class ClassfileVersionImpl
        extends AbstractElement
        implements ClassfileVersion {
    private final int majorVersion, minorVersion;

    public ClassfileVersionImpl(int majorVersion, int minorVersion) {
        this.majorVersion = majorVersion;
        this.minorVersion = minorVersion;
    }

    @Override
    public int majorVersion() {
        return majorVersion;
    }

    @Override
    public int minorVersion() {
        return minorVersion;
    }

    @Override
    public void writeTo(DirectClassBuilder builder) {
        builder.setVersion(majorVersion, minorVersion);
    }

    @Override
    public String toString() {
        return String.format("ClassfileVersion[majorVersion=%d, minorVersion=%d]", majorVersion, minorVersion);
    }
}
