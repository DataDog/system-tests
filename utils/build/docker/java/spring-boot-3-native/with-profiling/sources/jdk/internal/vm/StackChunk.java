/*
 * Copyright (c) 2019, 2022, Oracle and/or its affiliates. All rights reserved.
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

package jdk.internal.vm;

public final class StackChunk {
    public static void init() {}

    private StackChunk parent;
    private int size;    // in words
    private int sp;      // in words
    private int argsize; // bottom stack-passed arguments, in words

    // The stack itself is appended here by the VM, as well as some injected fields

    public StackChunk parent() { return parent; }
    public boolean isEmpty()   { return sp >= (size - argsize); }
}
