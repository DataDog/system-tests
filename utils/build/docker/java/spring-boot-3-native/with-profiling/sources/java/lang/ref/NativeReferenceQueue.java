/*
 * Copyright (c) 2021, 2022, Oracle and/or its affiliates. All rights reserved.
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

package java.lang.ref;

/**
 * An implementation of a ReferenceQueue that uses native monitors.
 * The use of java.util.concurrent.lock locks interacts with various mechanisms,
 * such as virtual threads and ForkJoinPool, that might not be appropriate for some
 * low-level mechanisms, in particular MethodType's weak intern set.
 */
final class NativeReferenceQueue<T> extends ReferenceQueue<T> {
    public NativeReferenceQueue() {
        super(0);
    }

    private static class Lock { };
    private final Lock lock = new Lock();

    @Override
    void signal() {
        lock.notifyAll();
    }
    @Override
    void await() throws InterruptedException {
        lock.wait();
    }

    @Override
    void await(long timeoutMillis) throws InterruptedException {
        lock.wait(timeoutMillis);
    }

    @Override
    boolean enqueue(Reference<? extends T> r) {
        synchronized(lock) {
            return enqueue0(r);
        }
    }

    @Override
    public Reference<? extends T> poll() {
        if (headIsNull())
            return null;

        synchronized(lock) {
            return poll0();
        }
    }

    @Override
    public Reference<? extends T> remove(long timeout)
            throws IllegalArgumentException, InterruptedException {
        if (timeout < 0)
            throw new IllegalArgumentException("Negative timeout value");
        if (timeout == 0)
            return remove();

        synchronized(lock) {
            return remove0(timeout);
        }
    }

    @Override
    public Reference<? extends T> remove() throws InterruptedException {
        synchronized(lock) {
            return remove0();
        }
    }
}
