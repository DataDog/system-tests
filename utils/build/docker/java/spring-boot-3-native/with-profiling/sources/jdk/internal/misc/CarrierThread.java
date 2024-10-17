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

import java.security.AccessControlContext;
import java.security.AccessController;
import java.security.PrivilegedAction;
import java.security.ProtectionDomain;
import java.util.concurrent.ForkJoinPool;
import java.util.concurrent.ForkJoinWorkerThread;
import jdk.internal.access.JavaLangAccess;
import jdk.internal.access.SharedSecrets;

/**
 * A ForkJoinWorkerThread that can be used as a carrier thread.
 */
public class CarrierThread extends ForkJoinWorkerThread {
    private static final JavaLangAccess JLA = SharedSecrets.getJavaLangAccess();
    private static final Unsafe U = Unsafe.getUnsafe();

    private static final ThreadGroup CARRIER_THREADGROUP = carrierThreadGroup();
    @SuppressWarnings("removal")
    private static final AccessControlContext INNOCUOUS_ACC = innocuousACC();

    private static final long CONTEXTCLASSLOADER;
    private static final long INHERITABLETHREADLOCALS;
    private static final long INHERITEDACCESSCONTROLCONTEXT;

    private boolean blocking;    // true if in blocking op

    public CarrierThread(ForkJoinPool pool) {
        super(CARRIER_THREADGROUP, pool, true);
        U.putReference(this, CONTEXTCLASSLOADER, ClassLoader.getSystemClassLoader());
        U.putReference(this, INHERITABLETHREADLOCALS, null);
        U.putReferenceRelease(this, INHERITEDACCESSCONTROLCONTEXT, INNOCUOUS_ACC);
    }

    /**
     * For use by {@link Blocker} to test if the thread is in a blocking operation.
     */
    boolean inBlocking() {
        //assert JLA.currentCarrierThread() == this;
        return blocking;
    }

    /**
     * For use by {@link Blocker} to mark the start of a blocking operation.
     */
    void beginBlocking() {
        //assert JLA.currentCarrierThread() == this && !blocking;
        blocking = true;
    }

    /**
     * For use by {@link Blocker} to mark the end of a blocking operation.
     */
    void endBlocking() {
        //assert JLA.currentCarrierThread() == this && blocking;
        blocking = false;
    }

    @Override
    public void setUncaughtExceptionHandler(UncaughtExceptionHandler ueh) { }

    @Override
    public void setContextClassLoader(ClassLoader cl) {
        throw new SecurityException("setContextClassLoader");
    }

    /**
     * The thread group for the carrier threads.
     */
    @SuppressWarnings("removal")
    private static final ThreadGroup carrierThreadGroup() {
        return AccessController.doPrivileged(new PrivilegedAction<ThreadGroup>() {
            public ThreadGroup run() {
                ThreadGroup group = JLA.currentCarrierThread().getThreadGroup();
                for (ThreadGroup p; (p = group.getParent()) != null; )
                    group = p;
                var carrierThreadsGroup = new ThreadGroup(group, "CarrierThreads");
                return carrierThreadsGroup;
            }
        });
    }

    /**
     * Return an AccessControlContext that doesn't support any permissions.
     */
    @SuppressWarnings("removal")
    private static AccessControlContext innocuousACC() {
        return new AccessControlContext(new ProtectionDomain[] {
                new ProtectionDomain(null, null)
        });
    }

    static {
        CONTEXTCLASSLOADER = U.objectFieldOffset(Thread.class,
                "contextClassLoader");
        INHERITABLETHREADLOCALS = U.objectFieldOffset(Thread.class,
                "inheritableThreadLocals");
        INHERITEDACCESSCONTROLCONTEXT = U.objectFieldOffset(Thread.class,
                "inheritedAccessControlContext");
    }
}
