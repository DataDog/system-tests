/*
 * Copyright (c) 2007, 2022, Oracle and/or its affiliates. All rights reserved.
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

import java.io.FileDescriptor;
import java.io.IOException;
import java.nio.channels.SelectableChannel;

abstract class FileDispatcher extends NativeDispatcher {

    public static final int NO_LOCK = -1;       // Failed to lock
    public static final int LOCKED = 0;         // Obtained requested lock
    public static final int RET_EX_LOCK = 1;    // Obtained exclusive lock
    public static final int INTERRUPTED = 2;    // Request interrupted

    /**
     * Sets or reports this file's position
     * If offset is -1, the current position is returned
     * otherwise the position is set to offset.
     */
    abstract long seek(FileDescriptor fd, long offset) throws IOException;

    abstract int force(FileDescriptor fd, boolean metaData) throws IOException;

    abstract int truncate(FileDescriptor fd, long size) throws IOException;

    abstract long size(FileDescriptor fd) throws IOException;

    abstract int lock(FileDescriptor fd, boolean blocking, long pos, long size,
                       boolean shared) throws IOException;

    abstract void release(FileDescriptor fd, long pos, long size)
        throws IOException;

    /**
     * Returns a dup of fd if a file descriptor is required for
     * memory-mapping operations, otherwise returns an invalid
     * FileDescriptor (meaning a newly allocated FileDescriptor)
     */
    abstract FileDescriptor duplicateForMapping(FileDescriptor fd)
        throws IOException;

    abstract boolean canTransferToDirectly(SelectableChannel sc);

    abstract boolean transferToDirectlyNeedsPositionLock();

    abstract boolean canTransferToFromOverlappedMap();

    abstract long allocationGranularity();

    abstract long map(FileDescriptor fd, int prot, long position, long length,
                      boolean isSync)
        throws IOException;

    abstract int unmap(long address, long length);

    abstract int maxDirectTransferSize();

    abstract long transferTo(FileDescriptor src, long position, long count,
                             FileDescriptor dst, boolean append);

    abstract long transferFrom(FileDescriptor src, FileDescriptor dst,
                               long position, long count, boolean append);

    abstract int setDirectIO(FileDescriptor fd, String path);
}
