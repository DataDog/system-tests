/*
 * Copyright (c) 2000, 2023, Oracle and/or its affiliates. All rights reserved.
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

// -- This file was mechanically generated: Do not edit! -- //

package java.nio;

import java.lang.foreign.MemorySegment;
import java.util.Objects;
import jdk.internal.misc.Unsafe;


sealed



class ByteBufferAsIntBufferL                  // package-private
    extends IntBuffer

    permits ByteBufferAsIntBufferRL

{



    protected final ByteBuffer bb;



    ByteBufferAsIntBufferL(ByteBuffer bb, MemorySegment segment) {   // package-private

        super(-1, 0,
              bb.remaining() >> 2,
              bb.remaining() >> 2, segment);
        this.bb = bb;
        // enforce limit == capacity
        int cap = this.capacity();
        this.limit(cap);
        int pos = this.position();
        assert (pos <= cap);
        address = bb.address;



    }

    ByteBufferAsIntBufferL(ByteBuffer bb,
                                     int mark, int pos, int lim, int cap,
                                     long addr, MemorySegment segment)
    {

        super(mark, pos, lim, cap, segment);
        this.bb = bb;
        address = addr;
        assert address >= bb.address;



    }

    @Override
    Object base() {
        return bb.hb;
    }

    public IntBuffer slice() {
        int pos = this.position();
        int lim = this.limit();
        int rem = (pos <= lim ? lim - pos : 0);
        long addr = byteOffset(pos);
        return new ByteBufferAsIntBufferL(bb, -1, 0, rem, rem, addr, segment);
    }

    @Override
    public IntBuffer slice(int index, int length) {
        Objects.checkFromIndexSize(index, length, limit());
        return new ByteBufferAsIntBufferL(bb,
                                                    -1,
                                                    0,
                                                    length,
                                                    length,
                                                    byteOffset(index), segment);
    }

    public IntBuffer duplicate() {
        return new ByteBufferAsIntBufferL(bb,
                                                    this.markValue(),
                                                    this.position(),
                                                    this.limit(),
                                                    this.capacity(),
                                                    address, segment);
    }

    public IntBuffer asReadOnlyBuffer() {

        return new ByteBufferAsIntBufferRL(bb,
                                                 this.markValue(),
                                                 this.position(),
                                                 this.limit(),
                                                 this.capacity(),
                                                 address, segment);



    }



    private int ix(int i) {
        int off = (int) (address - bb.address);
        return (i << 2) + off;
    }

    protected long byteOffset(long i) {
        return (i << 2) + address;
    }

    public int get() {
        int x = SCOPED_MEMORY_ACCESS.getIntUnaligned(session(), bb.hb, byteOffset(nextGetIndex()),
            false);
        return (x);
    }

    public int get(int i) {
        int x = SCOPED_MEMORY_ACCESS.getIntUnaligned(session(), bb.hb, byteOffset(checkIndex(i)),
            false);
        return (x);
    }











    public IntBuffer put(int x) {

        int y = (x);
        SCOPED_MEMORY_ACCESS.putIntUnaligned(session(), bb.hb, byteOffset(nextPutIndex()), y,
            false);
        return this;



    }

    public IntBuffer put(int i, int x) {

        int y = (x);
        SCOPED_MEMORY_ACCESS.putIntUnaligned(session(), bb.hb, byteOffset(checkIndex(i)), y,
            false);
        return this;



    }

    public IntBuffer compact() {

        int pos = position();
        int lim = limit();
        assert (pos <= lim);
        int rem = (pos <= lim ? lim - pos : 0);

        ByteBuffer db = bb.duplicate();
        db.limit(ix(lim));
        db.position(ix(0));
        ByteBuffer sb = db.slice();
        sb.position(pos << 2);
        sb.compact();
        position(rem);
        limit(capacity());
        discardMark();
        return this;



    }

    public boolean isDirect() {
        return bb.isDirect();
    }

    public boolean isReadOnly() {
        return false;
    }





































    public ByteOrder order() {




        return ByteOrder.LITTLE_ENDIAN;

    }






}
