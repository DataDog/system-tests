/*
 * Copyright (c) 2000, 2011, Oracle and/or its affiliates. All rights reserved.
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

package sun.nio.ch;

import jdk.internal.ref.Cleaner;


public interface DirectBuffer {

    // Use of the returned address must be guarded if this DirectBuffer
    // is backed by a memory session that is explicitly closeable.
    //
    // Failure to do this means the outcome is undefined including
    // silent unrelated memory mutation and JVM crashes.
    //
    // See JavaNioAccess for methods to safely acquire/release resources.
    public long address();

    public Object attachment();

    public Cleaner cleaner();

}
