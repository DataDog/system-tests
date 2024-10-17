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

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import jdk.jfr.internal.LogLevel;
import jdk.jfr.internal.LogTag;
import jdk.jfr.internal.Logger;
import jdk.jfr.internal.PlatformEventType;

/**
 * Class that holds periodic tasks.
 * <p>
 * This class is thread safe.
 */
final class TaskRepository {
    // Keeps periodic tasks in the order they were added by the user
    private final Map<LookupKey, EventTask> lookup = new LinkedHashMap<>();

    // An immutable copy that can be used to iterate over tasks.
    private List<EventTask> cache;

    public synchronized List<EventTask> getTasks() {
        if (cache == null) {
            cache = List.copyOf(lookup.values());
        }
        return cache;
    }

    public synchronized boolean removeTask(Runnable r) {
        EventTask pt = lookup.remove(new LookupKey(r));
        if (pt != null) {
            var eventType = pt.getEventType();
            // Invokes PeriodicEvents.setChanged()
            eventType.setEventHook(false);
            logTask("Removed", eventType);
            cache = null;
            return true;
        }
        return false;
    }

    public synchronized void add(EventTask task) {
        if (lookup.containsKey(task.getLookupKey())) {
            throw new IllegalArgumentException("Hook has already been added");
        }
        lookup.put(task.getLookupKey(), task);
        var eventType = task.getEventType();
        // Invokes PeriodicEvents.setChanged()
        eventType.setEventHook(true);
        logTask("Added", eventType);
        cache = null;
    }

    private void logTask(String action, PlatformEventType type) {
        if (type.isSystem()) {
            Logger.log(LogTag.JFR_SYSTEM, LogLevel.INFO, action + " periodic task for " + type.getLogName());
        } else {
            Logger.log(LogTag.JFR, LogLevel.INFO, action + " periodic task for " + type.getLogName());
        }
    }
}
