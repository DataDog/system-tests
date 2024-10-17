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
package jdk.jfr.internal.management;

import java.io.Closeable;
import java.io.IOException;

/**
 * Purpose of this class is to provide a synchronization point when stopping a
 * recording. Without it, a race can happen where a stream advances beyond the
 * last chunk of the recording.
 *
 * Code that is processing the stream calls check() and Unless the recording is
 * in the process of being stopped, it will just return. On the other hand, if
 * the recording is stopping, the thread waits and when it wakes up an end
 * position should have been set (last chunk position) beyond which the stream
 * processing should not continue.
 */
public final class StreamBarrier implements Closeable {

    private boolean activated = false;
    private long end = Long.MAX_VALUE;

    // Blocks thread until barrier is deactivated
    public synchronized void check() {
        while (activated) {
            try {
                this.wait();
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
    }

    public synchronized void setStreamEnd(long timestamp) {
        end = timestamp;
    }

    public synchronized long getStreamEnd() {
        return end;
    }

    public synchronized boolean hasStreamEnd() {
        return end != Long.MAX_VALUE;
    }

    public synchronized void activate() {
        activated = true;
    }

    @Override
    public synchronized void close() throws IOException {
        activated = false;
        this.notifyAll();
    }
}
