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
 * Event recording when an attempt to submit the task for a virtual thread failed.
 */
public class VirtualThreadSubmitFailedEvent extends Event {
    public long javaThreadId;
    public String exceptionMessage;
}
