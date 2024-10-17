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

import jdk.jfr.internal.JVM;
import jdk.jfr.internal.MetadataRepository;
import jdk.jfr.internal.Utils;

/**
 * Periodic task that flushes event data to disk.
 *<p>
 * The task is run once every second and after all other periodic events.
 * <p>
 * A flush interval of {@code Long.MAX_VALUE} means the event is disabled.
 */
final class FlushTask extends PeriodicTask {
    private volatile long flushInterval = Long.MAX_VALUE;

    public FlushTask() {
        super(new LookupKey(new Object()), "flush task");
    }

    @Override
    public void execute(long timestamp, PeriodicType periodicType) {
        MetadataRepository.getInstance().flush();
        Utils.notifyFlush();
    }

    @Override
    public boolean isSchedulable() {
        return true;
    }

    @Override
    protected long fetchPeriod() {
        return flushInterval;
    }

    public void setInterval(long millis) {
        // Don't accept shorter interval than 1 s
        long interval = millis < 1000 ? 1000 : millis;
        boolean needsNotify = interval < flushInterval;
        flushInterval = interval;
        PeriodicEvents.setChanged();
        if (needsNotify) {
            synchronized (JVM.CHUNK_ROTATION_MONITOR) {
                JVM.CHUNK_ROTATION_MONITOR.notifyAll();
            }
        }
    }
}
