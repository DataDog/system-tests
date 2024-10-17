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
package jdk.internal.event;

/**
 * Event recording that a virtual thread has been started.
 */
public class VirtualThreadStartEvent extends Event {
    private final static VirtualThreadStartEvent EVENT = new VirtualThreadStartEvent();

    /**
     * Returns {@code true} if event is enabled, {@code false} otherwise.
     */
    public static boolean isTurnedOn() {
        return EVENT.isEnabled();
    }

    public long javaThreadId;
}
