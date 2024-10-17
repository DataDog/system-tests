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

enum PeriodicType {
    /**
     * Event is running at the beginning of a chunk rotation.
     */
    BEGIN_CHUNK,
    /**
     * Event is running at an interval, for example, once every second.
     */
    INTERVAL,
    /**
     * Event is running at the end of a chunk rotation.
     */
    END_CHUNK
}