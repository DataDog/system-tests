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

/**
 * Periodic task that runs trusted code that doesn't require an access control
 * context.
 * <p>
 * This class can be removed once the Security Manager is no longer supported.
 */
final class JDKEventTask extends JavaEventTask {

    public JDKEventTask(Class<? extends Event> eventClass, Runnable runnable) {
        super(eventClass, runnable);
        if (!getEventType().isJDK()) {
            throw new InternalError("Must be a JDK event");
        }
        if (eventClass.getClassLoader() != null) {
            throw new SecurityException("Periodic task can only be registered for event classes that are loaded by the bootstrap class loader");
        }
        if (runnable.getClass().getClassLoader() != null) {
            throw new SecurityException("Runnable class must be loaded by the bootstrap class loader");
        }
    }

    @Override
    public void execute(long timestamp, PeriodicType periodicType) {
        getRunnable().run();
    }
}
