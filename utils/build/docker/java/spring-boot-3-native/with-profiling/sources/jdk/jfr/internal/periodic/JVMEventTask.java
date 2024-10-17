/*
 * Copyright (c) 2023, Oracle and/or its affiliates. All rights reserved.
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
package jdk.jfr.internal.periodic;

import java.util.concurrent.locks.Lock;
import java.util.concurrent.locks.ReentrantLock;

import jdk.jfr.internal.JVM;
import jdk.jfr.internal.PlatformEventType;

/**
 * Task for periodic events defined in the JVM.
 * <p>
 * This class guarantees that only one event can execute in native at a time.
 */
final class JVMEventTask extends EventTask {
    // java.util.concurrent lock is used to avoid JavaMonitorBlocked event from
    // synchronized block.
    private static final Lock lock = new ReentrantLock();

    public JVMEventTask(PlatformEventType eventType) {
        super(eventType, new LookupKey(eventType));
        if (!eventType.isJVM()) {
            throw new InternalError("Must be a JVM event");
        }
    }

    @Override
    public void execute(long timestamp, PeriodicType periodicType) {
        try {
            lock.lock();
            JVM.getJVM().emitEvent(getEventType().getId(), timestamp, periodicType.ordinal());
        } finally {
            lock.unlock();
        }
    }
}
