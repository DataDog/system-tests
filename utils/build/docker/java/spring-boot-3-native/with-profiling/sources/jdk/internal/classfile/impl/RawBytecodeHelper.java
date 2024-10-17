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

import java.nio.ByteBuffer;
import static jdk.internal.classfile.Classfile.ASTORE_3;
import static jdk.internal.classfile.Classfile.ISTORE;
import static jdk.internal.classfile.Classfile.LOOKUPSWITCH;
import static jdk.internal.classfile.Classfile.TABLESWITCH;
import static jdk.internal.classfile.Classfile.WIDE;

public final class RawBytecodeHelper {

    public static final int ILLEGAL = -1;

    private static final byte[] LENGTHS = new byte[] {
        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 3, 2, 3, 3, 2 | (4 << 4), 2 | (4 << 4), 2 | (4 << 4), 2 | (4 << 4), 2 | (4 << 4), 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
        2 | (4 << 4), 2 | (4 << 4), 2 | (4 << 4), 2 | (4 << 4), 2 | (4 << 4), 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 3 | (6 << 4), 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 2 | (4 << 4), 0, 0, 1, 1, 1,
        1, 1, 1, 3, 3, 3, 3, 3, 3, 3, 5, 5, 3, 2, 3, 1, 1, 3, 3, 1, 1, 0, 4, 3, 3, 5, 5, 0, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 1, 4, 4, 4, 2, 4, 3, 3, 0, 0, 1, 3, 2, 3, 3, 3, 1, 2, 1,
        -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1
    };

    public static boolean isStoreIntoLocal(int code) {
        return (ISTORE <= code && code <= ASTORE_3);
    }

    public static int align(int n) {
        return (n + 3) & ~3;
    }

    private final ByteBuffer bytecode;
    public int bci, nextBci, endBci;
    public int rawCode;
    public boolean isWide;

    public RawBytecodeHelper(ByteBuffer bytecode) {
        this.bytecode = bytecode;
        this.bci = 0;
        this.nextBci = 0;
        this.endBci = bytecode.capacity();
    }

    public boolean isLastBytecode() {
        return nextBci >= endBci;
    }

    public int getShort(int bci) {
        return bytecode.getShort(bci);
    }

    public int dest() {
        return bci + getShort(bci + 1);
    }

    public int getInt(int bci) {
        return bytecode.getInt(bci);
    }

    public int destW() {
        return bci + getInt(bci + 1);
    }

    public int getIndexU1() {
        return bytecode.get(bci + 1) & 0xff;
    }

    public int getU1(int bci) {
        return bytecode.get(bci) & 0xff;
    }

    public int rawNext(int jumpTo) {
        this.nextBci = jumpTo;
        return rawNext();
    }

    public int rawNext() {
        bci = nextBci;
        int code = bytecode.get(bci) & 0xff;
        int len = LENGTHS[code] & 0xf;
        if (len > 0 && (bci <= endBci - len)) {
            isWide = false;
            nextBci += len;
            if (nextBci <= bci) {
                code = ILLEGAL;
            }
            rawCode = code;
            return code;
        } else {
            len = switch (bytecode.get(bci) & 0xff) {
                case WIDE -> {
                    if (bci + 1 >= endBci) {
                        yield -1;
                    }
                    yield LENGTHS[bytecode.get(bci + 1) & 0xff] >> 4;
                }
                case TABLESWITCH -> {
                    int aligned_bci = align(bci + 1);
                    if (aligned_bci + 3 * 4 >= endBci) {
                        yield -1;
                    }
                    int lo = bytecode.getInt(aligned_bci + 1 * 4);
                    int hi = bytecode.getInt(aligned_bci + 2 * 4);
                    int l = aligned_bci - bci + (3 + hi - lo + 1) * 4;
                    if (l > 0) yield l; else yield -1;
                }
                case LOOKUPSWITCH -> {
                    int aligned_bci = align(bci + 1);
                    if (aligned_bci + 2 * 4 >= endBci) {
                        yield -1;
                    }
                    int npairs = bytecode.getInt(aligned_bci + 4);
                    int l = aligned_bci - bci + (2 + 2 * npairs) * 4;
                    if (l > 0) yield l; else yield -1;
                }
                default ->
                    0;
            };
            if (len <= 0 || (bci > endBci - len) || (bci - len >= nextBci)) {
                code = ILLEGAL;
            } else {
                nextBci += len;
                isWide = false;
                if (code == WIDE) {
                    if (bci + 1 >= endBci) {
                        code = ILLEGAL;
                    } else {
                        code = bytecode.get(bci + 1) & 0xff;
                        isWide = true;
                    }
                }
            }
            rawCode = code;
            return code;
        }
    }

    public int getIndex() {
        return (isWide) ? getIndexU2Raw(bci + 2) : getIndexU1();
    }

    public int getIndexU2() {
        return getIndexU2Raw(bci + 1);
    }

    public int getIndexU2Raw(int bci) {
        return bytecode.getShort(bci) & 0xffff;
    }
}
