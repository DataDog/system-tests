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

package jdk.jfr.events;

import jdk.jfr.Category;
import jdk.jfr.Label;
import jdk.jfr.Name;
import jdk.jfr.internal.MirrorEvent;

@Category("Java Application")
@Label("Virtual Thread Start")
@Name("jdk.VirtualThreadStart")
@MirrorEvent(className = "jdk.internal.event.VirtualThreadStartEvent")
public final class VirtualThreadStartEvent extends AbstractJDKEvent {

    @Label("Thread Id")
    public long javaThreadId;

}
