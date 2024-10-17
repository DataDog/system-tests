/*
 * Copyright (c) 2018, 2022, Oracle and/or its affiliates. All rights reserved.
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

import java.util.concurrent.TimeUnit;
import java.util.concurrent.RejectedExecutionException;
import jdk.internal.access.JavaLangAccess;
import jdk.internal.access.SharedSecrets;

/**
 * Defines static methods to support execution in the context of a virtual thread.
 */
public final class VirtualThreads {
    private static final JavaLangAccess JLA;
    static {
        JLA = SharedSecrets.getJavaLangAccess();
        if (JLA == null) {
            throw new InternalError("JavaLangAccess not setup");
        }
    }
    private VirtualThreads() { }

    /**
     * Parks the current virtual thread until it is unparked or interrupted.
     * If already unparked then the parking permit is consumed and this method
     * completes immediately (meaning it doesn't yield). It also completes
     * immediately if the interrupt status is set.
     * @throws WrongThreadException if the current thread is not a virtual thread
     */
    public static void park() {
        JLA.parkVirtualThread();
    }

    /**
     * Parks the current virtual thread up to the given waiting time or until it
     * is unparked or interrupted. If already unparked then the parking permit is
     * consumed and this method completes immediately (meaning it doesn't yield).
     * It also completes immediately if the interrupt status is set or the waiting
     * time is {@code <= 0}.
     * @param nanos the maximum number of nanoseconds to wait
     * @throws WrongThreadException if the current thread is not a virtual thread
     */
    public static void park(long nanos) {
        JLA.parkVirtualThread(nanos);
    }

    /**
     * Parks the current virtual thread until the given deadline or until is is
     * unparked or interrupted. If already unparked then the parking permit is
     * consumed and this method completes immediately (meaning it doesn't yield).
     * It also completes immediately if the interrupt status is set or the
     * deadline has past.
     * @param deadline absolute time, in milliseconds, from the epoch
     * @throws WrongThreadException if the current thread is not a virtual thread
     */
    public static void parkUntil(long deadline) {
        long millis = deadline - System.currentTimeMillis();
        long nanos = TimeUnit.NANOSECONDS.convert(millis, TimeUnit.MILLISECONDS);
        park(nanos);
    }

    /**
     * Re-enables a virtual thread for scheduling. If the thread was parked then
     * it will be unblocked, otherwise its next attempt to park will not block
     * @param thread the virtual thread to unpark
     * @throws IllegalArgumentException if the thread is not a virtual thread
     * @throws RejectedExecutionException if the scheduler cannot accept a task
     */
    public static void unpark(Thread thread) {
        JLA.unparkVirtualThread(thread);
    }
}
