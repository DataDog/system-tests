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

import java.security.AccessControlContext;
import java.security.AccessController;
import java.security.PrivilegedAction;
import java.util.Objects;

import jdk.jfr.Event;
import jdk.jfr.internal.LogLevel;
import jdk.jfr.internal.LogTag;
import jdk.jfr.internal.Logger;

/**
 * Class to be used with user-defined events that runs untrusted code.
 * <p>
 * This class can be removed once the Security Manager is no longer supported.
 */
final class UserEventTask extends JavaEventTask {
    @SuppressWarnings("removal")
    private final AccessControlContext controlContext;

    public UserEventTask(@SuppressWarnings("removal") AccessControlContext controlContext, Class<? extends Event> eventClass, Runnable runnable) {
        super(eventClass, runnable);
        this.controlContext = Objects.requireNonNull(controlContext);
    }

    @SuppressWarnings("removal")
    @Override
    public void execute(long timestamp, PeriodicType periodicType) {
        AccessController.doPrivileged((PrivilegedAction<Void>) () -> {
            execute();
            return null;
        }, controlContext);
    }

    private void execute() {
        try {
            getRunnable().run();
            if (Logger.shouldLog(LogTag.JFR_EVENT, LogLevel.DEBUG)) {
                Logger.log(LogTag.JFR_EVENT, LogLevel.DEBUG, "Executed periodic task for " + getEventType().getLogName());
            }
        } catch (Throwable t) {
            // Prevent malicious user to propagate exception callback in the wrong context
            Logger.log(LogTag.JFR_EVENT, LogLevel.WARN, "Exception occurred during execution of period task for " + getEventType().getLogName());
        }
    }
}
