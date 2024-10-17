/*
 * Copyright (c) 2022, Oracle and/or its affiliates. All rights reserved.
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
package jdk.internal.access;

import java.util.concurrent.ForkJoinPool;

public interface JavaUtilConcurrentFJPAccess {
    long beginCompensatedBlock(ForkJoinPool pool);
    void endCompensatedBlock(ForkJoinPool pool, long post);
}
