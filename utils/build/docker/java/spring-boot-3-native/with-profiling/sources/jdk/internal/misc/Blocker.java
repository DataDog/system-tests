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

package jdk.internal.misc;

import java.util.concurrent.ForkJoinPool;
import jdk.internal.access.JavaLangAccess;
import jdk.internal.access.JavaUtilConcurrentFJPAccess;
import jdk.internal.access.SharedSecrets;

/**
 * Defines static methods to mark the beginning and end of a possibly blocking
 * operation. The methods are intended to be used with try-finally as follows:
 * {@snippet lang=java :
 *     long comp = Blocker.begin();
 *     try {
 *         // blocking operation
 *     } finally {
 *         Blocker.end(comp);
 *     }
 * }
 * If invoked from a virtual thread and the underlying carrier thread is a
 * CarrierThread then the code in the block runs as if it were in run in
 * ForkJoinPool.ManagedBlocker. This means the pool can be expanded to support
 * additional parallelism during the blocking operation.
 */
public class Blocker {
    private static final JavaLangAccess JLA;
    static {
        JLA = SharedSecrets.getJavaLangAccess();
        if (JLA == null) {
            throw new InternalError("JavaLangAccess not setup");
        }
    }

    private Blocker() { }

    private static Thread currentCarrierThread() {
        return JLA.currentCarrierThread();
    }

    /**
     * Marks the beginning of a possibly blocking operation.
     * @return the return value from the attempt to compensate or -1 if not attempted
     */
    public static long begin() {
        if (VM.isBooted()
                && currentCarrierThread() instanceof CarrierThread ct && !ct.inBlocking()) {
            ct.beginBlocking();
            boolean completed = false;
            try {
                long comp = ForkJoinPools.beginCompensatedBlock(ct.getPool());
                assert currentCarrierThread() == ct;
                completed = true;
                return comp;
            } finally {
                if (!completed) {
                    ct.endBlocking();
                }
            }
        }
        return -1;
    }

    /**
     * Marks the beginning of a possibly blocking operation.
     * @param blocking true if the operation may block, otherwise false
     * @return the return value from the attempt to compensate, -1 if not attempted
     * or blocking is false
     */
    public static long begin(boolean blocking) {
        return (blocking) ? begin() : -1;
    }

    /**
     * Marks the end of an operation that may have blocked.
     * @param compensateReturn the value returned by the begin method
     */
    public static void end(long compensateReturn) {
        if (compensateReturn >= 0) {
            assert currentCarrierThread() instanceof CarrierThread ct && ct.inBlocking();
            CarrierThread ct = (CarrierThread) currentCarrierThread();
            ForkJoinPools.endCompensatedBlock(ct.getPool(), compensateReturn);
            ct.endBlocking();
        }
    }

    /**
     * Defines static methods to invoke non-public ForkJoinPool methods via the
     * shared secret support.
     */
    private static class ForkJoinPools {
        private static final JavaUtilConcurrentFJPAccess FJP_ACCESS =
                SharedSecrets.getJavaUtilConcurrentFJPAccess();
        static long beginCompensatedBlock(ForkJoinPool pool) {
            return FJP_ACCESS.beginCompensatedBlock(pool);
        }
        static void endCompensatedBlock(ForkJoinPool pool, long post) {
            FJP_ACCESS.endCompensatedBlock(pool, post);
        }
    }

}
