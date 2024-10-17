/*
 * Copyright (c) 2021, Oracle and/or its affiliates. All rights reserved.
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

import java.io.IOException;

/*
 * Provides access to the Linux eventfd object.
 */
final class EventFD {
    private final int efd;

    /**
     * Creates a blocking eventfd object with initial value zero.
     */
    EventFD() throws IOException {
        efd = eventfd0();
    }

    int efd() {
        return efd;
    }

    void set() throws IOException {
        set0(efd);
    }

    void reset() throws IOException {
        IOUtil.drain(efd);
    }

    void close() throws IOException {
        FileDispatcherImpl.closeIntFD(efd);
    }

    private static native int eventfd0() throws IOException;

    /**
     * Writes the value 1 to the eventfd object as a long in the
     * native byte order of the platform.
     *
     * @param the integral eventfd file descriptor
     * @return the number of bytes written; should equal 8
     */
    private static native int set0(int efd) throws IOException;

    static {
        IOUtil.load();
    }
}
