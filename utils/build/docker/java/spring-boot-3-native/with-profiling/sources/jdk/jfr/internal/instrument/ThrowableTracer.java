/*
 * Copyright (c) 2012, 2022, Oracle and/or its affiliates. All rights reserved.
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

package jdk.jfr.internal.instrument;

import java.util.concurrent.atomic.AtomicLong;

import jdk.jfr.events.EventConfigurations;
import jdk.jfr.events.ErrorThrownEvent;
import jdk.jfr.events.ExceptionThrownEvent;
import jdk.jfr.internal.event.EventConfiguration;

public final class ThrowableTracer {

    private static final AtomicLong numThrowables = new AtomicLong();

    public static void traceError(Error e, String message) {
        if (e instanceof OutOfMemoryError) {
            return;
        }
        long timestamp = EventConfiguration.timestamp();

        EventConfiguration eventConfiguration1 = EventConfigurations.ERROR_THROWN;
        if (eventConfiguration1.isEnabled()) {
            ErrorThrownEvent.commit(timestamp, 0L, message, e.getClass());
        }
        EventConfiguration eventConfiguration2 = EventConfigurations.EXCEPTION_THROWN;
        if (eventConfiguration2.isEnabled()) {
            ExceptionThrownEvent.commit(timestamp, 0L, message, e.getClass());
        }
        numThrowables.incrementAndGet();
    }

    public static void traceThrowable(Throwable t, String message) {
        EventConfiguration eventConfiguration = EventConfigurations.EXCEPTION_THROWN;
        if (eventConfiguration.isEnabled()) {
            long timestamp = EventConfiguration.timestamp();
            ExceptionThrownEvent.commit(timestamp, 0L, message, t.getClass());
        }
        numThrowables.incrementAndGet();
    }

    public static long numThrowables() {
        return numThrowables.get();
    }
}
