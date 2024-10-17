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

import jdk.internal.classfile.BufWriter;
import jdk.internal.classfile.Label;
import jdk.internal.classfile.constantpool.Utf8Entry;

public class AbstractBoundLocalVariable
        extends AbstractElement {
    protected final CodeImpl code;
    protected final int offset;
    private Utf8Entry nameEntry;
    private Utf8Entry secondaryEntry;

    public AbstractBoundLocalVariable(CodeImpl code, int offset) {
        this.code = code;
        this.offset = offset;
    }

    protected int nameIndex() {
        return code.classReader.readU2(offset + 4);
    }

    public Utf8Entry name() {
        if (nameEntry == null)
            nameEntry = (Utf8Entry) code.constantPool().entryByIndex(nameIndex());
        return nameEntry;
    }

    protected int secondaryIndex() {
        return code.classReader.readU2(offset + 6);
    }

    protected Utf8Entry secondaryEntry() {
        if (secondaryEntry == null)
            secondaryEntry = (Utf8Entry) code.constantPool().entryByIndex(secondaryIndex());
        return secondaryEntry;
    }

    public Label startScope() {
        return code.getLabel(startPc());
    }

    public Label endScope() {
        return code.getLabel(startPc() + length());
    }

    public int startPc() {
        return code.classReader.readU2(offset);
    }

    public int length() {
        return code.classReader.readU2(offset+2);
    }

    public int slot() {
        return code.classReader.readU2(offset + 8);
    }

    public boolean writeTo(BufWriter b) {
        var lc = ((BufWriterImpl)b).labelContext();
        int startBci = lc.labelToBci(startScope());
        int endBci = lc.labelToBci(endScope());
        if (startBci == -1 || endBci == -1) {
            return false;
        }
        int length = endBci - startBci;
        b.writeU2(startBci);
        b.writeU2(length);
        if (b.canWriteDirect(code.constantPool())) {
            b.writeU2(nameIndex());
            b.writeU2(secondaryIndex());
        }
        else {
            b.writeIndex(name());
            b.writeIndex(secondaryEntry());
        }
        b.writeU2(slot());
        return true;
    }
}
