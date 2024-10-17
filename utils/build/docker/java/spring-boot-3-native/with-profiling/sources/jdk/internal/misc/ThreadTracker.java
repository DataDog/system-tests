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

import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Tracks threads to help detect reentrancy without using ThreadLocal variables.
 * A thread invokes the {@code begin} or {@code tryBegin} methods at the start
 * of a block, and the {@code end} method at the end of a block.
 */
public class ThreadTracker {

    /**
     * A reference to a Thread that is suitable for use as a key in a collection.
     * The hashCode/equals methods do not invoke the Thread hashCode/equals method
     * as they may run arbitrary code and/or leak references to Thread objects.
     */
    private record ThreadRef(Thread thread) {
        @Override
        public int hashCode() {
            return Long.hashCode(thread.threadId());
        }
        @Override
        public boolean equals(Object obj) {
            return (obj instanceof ThreadRef other)
                    && this.thread == other.thread;
        }
    }

    private final Set<ThreadRef> threads = ConcurrentHashMap.newKeySet();

    /**
     * Adds the current thread to thread set if not already in the set.
     * Returns a key to remove the thread or {@code null} if already in the set.
     */
    public Object tryBegin() {
        var threadRef = new ThreadRef(Thread.currentThread());
        return threads.add(threadRef) ? threadRef : null;
    }

    /**
     * Adds the current thread to thread set if not already in the set.
     * Returns a key to remove the thread.
     */
    public Object begin() {
        var threadRef = new ThreadRef(Thread.currentThread());
        boolean added = threads.add(threadRef);
        assert added;
        return threadRef;
    }

    /**
     * Removes the thread identified by the key from the thread set.
     */
    public void end(Object key) {
        var threadRef = (ThreadRef) key;
        assert threadRef.thread() == Thread.currentThread();
        boolean removed = threads.remove(threadRef);
        assert removed;
    }

    /**
     * Returns true if the given thread is tracked.
     */
    public boolean contains(Thread thread) {
        var threadRef = new ThreadRef(thread);
        return threads.contains(threadRef);
    }
}
