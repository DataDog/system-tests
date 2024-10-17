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
package java.lang;

/**
 * Base class for virtual thread implementations.
 */
sealed abstract class BaseVirtualThread extends Thread
        permits VirtualThread, ThreadBuilders.BoundVirtualThread {

    /**
     * Initializes a virtual Thread.
     *
     * @param name thread name, can be null
     * @param characteristics thread characteristics
     * @param bound true when bound to an OS thread
     */
    BaseVirtualThread(String name, int characteristics, boolean bound) {
        super(name, characteristics, bound);
    }

    /**
     * Parks the current virtual thread until the parking permit is available or
     * the thread is interrupted.
     *
     * The behavior of this method when the current thread is not this thread
     * is not defined.
     */
    abstract void park();

    /**
     * Parks current virtual thread up to the given waiting time until the parking
     * permit is available or the thread is interrupted.
     *
     * The behavior of this method when the current thread is not this thread
     * is not defined.
     */
    abstract void parkNanos(long nanos);

    /**
     * Makes available the parking permit to the given this virtual thread.
     */
    abstract void unpark();
}

