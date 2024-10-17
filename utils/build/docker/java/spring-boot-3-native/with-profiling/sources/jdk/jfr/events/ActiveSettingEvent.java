/*
 * Copyright (c) 2016, 2019, Oracle and/or its affiliates. All rights reserved.
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
import jdk.jfr.StackTrace;
import jdk.jfr.internal.Type;

@Name(Type.EVENT_NAME_PREFIX + "ActiveSetting")
@Label("Recording Setting")
@Category("Flight Recorder")
@StackTrace(false)
public final class ActiveSettingEvent extends AbstractJDKEvent {

    // The order of these fields must be the same as the parameters in
    // commit(... , long, String, String)

    @Label("Event Id")
    public long id;

    @Label("Setting Name")
    public String name;

    @Label("Setting Value")
    public String value;

    public static void commit(long startTime, long duration, long id, String name, String value) {
        // Generated
    }

    public static boolean enabled() {
        return false; // Generated
    }
}
