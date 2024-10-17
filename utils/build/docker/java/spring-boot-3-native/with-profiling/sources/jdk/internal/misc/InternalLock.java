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

package jdk.internal.misc;

import java.util.concurrent.locks.ReentrantLock;

/**
 * A reentrant mutual exclusion lock for internal use. The lock does not
 * implement {@link java.util.concurrent.locks.Lock} or extend {@link
 * java.util.concurrent.locks.ReentrantLock} so that it can be distinguished
 * from lock objects accessible to subclasses of {@link java.io.Reader} and
 * {@link java.io.Writer} (it is possible to create a Reader that uses a
 * lock object of type ReentrantLock for example).
 */
public class InternalLock {
    private static final boolean CAN_USE_INTERNAL_LOCK;
    static {
        String s = System.getProperty("jdk.io.useMonitors");
        if (s != null && (s.isEmpty() || s.equals("true"))) {
            CAN_USE_INTERNAL_LOCK = false;
        } else {
            CAN_USE_INTERNAL_LOCK = true;
        }
    }

    private final ReentrantLock lock;

    private InternalLock() {
        this.lock = new ReentrantLock();
    }

    /**
     * Returns a new InternalLock or null.
     */
    public static InternalLock newLockOrNull() {
        return (CAN_USE_INTERNAL_LOCK) ? new InternalLock() : null;
    }

    /**
     * Returns a new InternalLock or the given object.
     */
    public static Object newLockOr(Object obj) {
        return (CAN_USE_INTERNAL_LOCK) ? new InternalLock() : obj;
    }

    public boolean tryLock() {
        return lock.tryLock();
    }

    public void lock() {
        lock.lock();
    }

    public void unlock() {
        lock.unlock();
    }

    public boolean isHeldByCurrentThread() {
        return lock.isHeldByCurrentThread();
    }
}
