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

import java.util.ArrayList;
import java.util.List;

/**
 * Class that holds periodic tasks that run at the same time.
 * <p>
 * For example, events with period 1s, 3s and 7s can run when the 1s event run,
 * not every time, but some of the time. An event with period 1.5s would not
 * belong to the same batch since it would need to run between the 1s interval.
 * <p>
 * This class should only be accessed from the periodic task thread.
 */
final class Batch {
    private final List<PeriodicTask> tasks = new ArrayList<>();
    private final long period;
    private long delta;

    public Batch(long period) {
        this.period = period;
    }

    public long getDelta() {
        return delta;
    }

    public void setDelta(long delta) {
        this.delta = delta;
    }

    public long getPeriod() {
        return period;
    }

    public List<PeriodicTask> getTasks() {
        return tasks;
    }

    public void add(PeriodicTask task) {
        task.setBatch(this);
        tasks.add(task);
    }

    public void clear() {
        tasks.clear();
    }

    public boolean isEmpty() {
        return tasks.isEmpty();
    }
}