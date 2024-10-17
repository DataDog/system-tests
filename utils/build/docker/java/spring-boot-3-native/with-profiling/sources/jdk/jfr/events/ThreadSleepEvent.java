/*
 * Copyright (c) 2020, 2022, Oracle and/or its affiliates. All rights reserved.
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

package jdk.jfr.events;

import jdk.jfr.Category;
import jdk.jfr.Label;
import jdk.jfr.Name;
import jdk.jfr.Timespan;
import jdk.jfr.internal.MirrorEvent;

@Category("Java Application")
@Label("Java Thread Sleep")
@Name("jdk.ThreadSleep")
@MirrorEvent(className = "jdk.internal.event.ThreadSleepEvent")
public final class ThreadSleepEvent extends AbstractJDKEvent {
    @Label("Sleep Time")
    @Timespan(Timespan.NANOSECONDS)
    public long time;
}
