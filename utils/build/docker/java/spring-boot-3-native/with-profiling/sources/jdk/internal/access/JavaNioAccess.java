/*
 * Copyright (c) 2007, 2022, Oracle and/or its affiliates. All rights reserved.
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

package jdk.internal.access;

import jdk.internal.access.foreign.UnmapperProxy;
import jdk.internal.misc.VM.BufferPool;

import java.lang.foreign.MemorySegment;
import java.io.FileDescriptor;
import java.nio.Buffer;
import java.nio.ByteBuffer;

public interface JavaNioAccess {

    /**
     * Used by {@code jdk.internal.misc.VM}.
     */
    BufferPool getDirectBufferPool();

    /**
     * Constructs a direct ByteBuffer referring to the block of memory starting
     * at the given memory address and extending {@code cap} bytes.
     * The {@code ob} parameter is an arbitrary object that is attached
     * to the resulting buffer.
     * Used by {@code jdk.internal.foreignMemorySegmentImpl}.
     */
    ByteBuffer newDirectByteBuffer(long addr, int cap, Object obj, MemorySegment segment);

    /**
     * Constructs a mapped ByteBuffer referring to the block of memory starting
     * at the given memory address and extending {@code cap} bytes.
     * The {@code ob} parameter is an arbitrary object that is attached
     * to the resulting buffer. The {@code sync} and {@code fd} parameters of the mapped
     * buffer are derived from the {@code UnmapperProxy}.
     * Used by {@code jdk.internal.foreignMemorySegmentImpl}.
     */
    ByteBuffer newMappedByteBuffer(UnmapperProxy unmapperProxy, long addr, int cap, Object obj, MemorySegment segment);

    /**
     * Constructs an heap ByteBuffer with given backing array, offset, capacity and segment.
     * Used by {@code jdk.internal.foreignMemorySegmentImpl}.
     */
    ByteBuffer newHeapByteBuffer(byte[] hb, int offset, int capacity, MemorySegment segment);

    /**
     * Used by {@code jdk.internal.foreign.Utils}.
     */
    Object getBufferBase(Buffer bb);

    /**
     * Used by {@code jdk.internal.foreign.Utils}.
     */
    long getBufferAddress(Buffer buffer);

    /**
     * Used by {@code jdk.internal.foreign.Utils}.
     */
    UnmapperProxy unmapper(Buffer buffer);

    /**
     * Used by {@code jdk.internal.foreign.AbstractMemorySegmentImpl} and byte buffer var handle views.
     */
    MemorySegment bufferSegment(Buffer buffer);

    /**
     * Used by operations to make a buffer's session non-closeable
     * (for the duration of the operation) by acquiring the session.
     * {@snippet lang = java:
     * acquireSession(buffer);
     * try {
     *     performOperation(buffer);
     * } finally {
     *     releaseSession(buffer);
     * }
     *}
     *
     * @see #releaseSession(Buffer)
     */
    void acquireSession(Buffer buffer);

    void releaseSession(Buffer buffer);

    boolean isThreadConfined(Buffer buffer);

    boolean hasSession(Buffer buffer);

    /**
     * Used by {@code jdk.internal.foreign.MappedMemorySegmentImpl} and byte buffer var handle views.
     */
    void force(FileDescriptor fd, long address, boolean isSync, long offset, long size);

    /**
     * Used by {@code jdk.internal.foreign.MappedMemorySegmentImpl} and byte buffer var handle views.
     */
    void load(long address, boolean isSync, long size);

    /**
     * Used by {@code jdk.internal.foreign.MappedMemorySegmentImpl}.
     */
    void unload(long address, boolean isSync, long size);

    /**
     * Used by {@code jdk.internal.foreign.MappedMemorySegmentImpl} and byte buffer var handle views.
     */
    boolean isLoaded(long address, boolean isSync, long size);

    /**
     * Used by {@code jdk.internal.foreign.NativeMemorySegmentImpl}.
     */
    void reserveMemory(long size, long cap);

    /**
     * Used by {@code jdk.internal.foreign.NativeMemorySegmentImpl}.
     */
    void unreserveMemory(long size, long cap);

    /**
     * Used by {@code jdk.internal.foreign.NativeMemorySegmentImpl}.
     */
    int pageSize();
}
