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
import jdk.jfr.Description;
import jdk.jfr.Label;
import jdk.jfr.Name;
import jdk.jfr.internal.MirrorEvent;

@Category({"Java Development Kit", "Threading"})
@Label("Virtual Thread Submit Failed")
@Name("jdk.VirtualThreadSubmitFailed")
@Description("Submit of task for virtual thread failed")
@MirrorEvent(className = "jdk.internal.event.VirtualThreadSubmitFailedEvent")
public final class VirtualThreadSubmitFailedEvent extends AbstractJDKEvent {

    @Label("Thread Id")
    public long javaThreadId;

    @Label("Exception Message")
    public String exceptionMessage;

}
