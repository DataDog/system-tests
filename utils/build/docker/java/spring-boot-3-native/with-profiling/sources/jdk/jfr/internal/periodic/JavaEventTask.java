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

import jdk.jfr.Event;
import jdk.jfr.EventType;
import jdk.jfr.internal.MetadataRepository;
import jdk.jfr.internal.PlatformEventType;
import jdk.jfr.internal.PrivateAccess;
/**
 * Base class for periodic Java events.
 */
abstract class JavaEventTask extends EventTask {
    private final Runnable runnable;

    public JavaEventTask(Class<? extends Event> eventClass, Runnable runnable) {
        super(toPlatformEventType(eventClass), new LookupKey(runnable));
        this.runnable = runnable;
        if (getEventType().isJVM()) {
            throw new InternalError("Must not be a JVM event");
        }
    }

    private static PlatformEventType toPlatformEventType(Class<? extends Event> eventClass) {
        EventType eventType = MetadataRepository.getInstance().getEventType(eventClass);
        return PrivateAccess.getInstance().getPlatformEventType(eventType);
    }

    protected final Runnable getRunnable() {
        return runnable;
    }
}
