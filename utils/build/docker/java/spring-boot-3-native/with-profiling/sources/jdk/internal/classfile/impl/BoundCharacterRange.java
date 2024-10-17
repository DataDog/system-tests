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

import jdk.internal.classfile.Label;
import jdk.internal.classfile.instruction.CharacterRange;

public final class BoundCharacterRange
        extends AbstractElement
        implements CharacterRange {

    private final CodeImpl code;
    private final int offset;

    public BoundCharacterRange(CodeImpl code, int offset) {
        this.code = code;
        this.offset = offset;
    }

    int startPc() {
        return code.classReader.readU2(offset);
    }

    int endPc() {
        return code.classReader.readU2(offset + 2);
    }

    @Override
    public int characterRangeStart() {
        return code.classReader.readInt(offset + 4);
    }

    @Override
    public int characterRangeEnd() {
        return code.classReader.readInt(offset + 8);
    }

    @Override
    public int flags() {
        return code.classReader.readU2(offset + 12);
    }

    @Override
    public Label startScope() {
        return code.getLabel(startPc());
    }

    @Override
    public Label endScope() {
        return code.getLabel(endPc() + 1);
    }

    @Override
    public void writeTo(DirectCodeBuilder builder) {
        builder.addCharacterRange(this);
    }

    @Override
    public String toString() {
        return String.format("CharacterRange[startScope=%s, endScope=%s, characterRangeStart=%s, characterRangeEnd=%s, flags=%d]",
                startScope(), endScope(), characterRangeStart(), characterRangeEnd(), flags());
    }
}
