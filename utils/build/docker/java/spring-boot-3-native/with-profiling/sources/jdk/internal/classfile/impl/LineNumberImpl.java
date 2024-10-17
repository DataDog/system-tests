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

import jdk.internal.classfile.instruction.LineNumber;

public final class LineNumberImpl
        extends AbstractElement
        implements LineNumber {
    private static final int INTERN_LIMIT = 1000;
    private static final LineNumber[] internCache = new LineNumber[INTERN_LIMIT];
    static {
        for (int i=0; i<INTERN_LIMIT; i++)
            internCache[i] = new LineNumberImpl(i);
    }

    private final int line;

    private LineNumberImpl(int line) {
        this.line = line;
    }

    public static LineNumber of(int line) {
        return (line < INTERN_LIMIT)
               ? internCache[line]
               : new LineNumberImpl(line);
    }

    @Override
    public int line() {
        return line;
    }

    @Override
    public void writeTo(DirectCodeBuilder writer) {
        writer.setLineNumber(line);
    }

    @Override
    public String toString() {
        return String.format("LineNumber[line=%d]", line);
    }
}

