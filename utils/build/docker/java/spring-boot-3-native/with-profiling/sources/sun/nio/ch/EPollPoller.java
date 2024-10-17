/*
 * Copyright (c) 2017, 2022, Oracle and/or its affiliates. All rights reserved.
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
import static sun.nio.ch.EPoll.*;

/**
 * Poller implementation based on the epoll facility.
 */

class EPollPoller extends Poller {
    private static final int MAX_EVENTS_TO_POLL = 512;
    private static final int ENOENT = 2;

    private final int epfd;
    private final int event;
    private final long address;

    EPollPoller(boolean read) throws IOException {
        super(read);
        this.epfd = EPoll.create();
        this.event = (read) ? EPOLLIN : EPOLLOUT;
        this.address = EPoll.allocatePollArray(MAX_EVENTS_TO_POLL);
    }

    @Override
    int fdVal() {
        return epfd;
    }

    @Override
    void implRegister(int fdVal) throws IOException {
        // re-arm
        int err = EPoll.ctl(epfd, EPOLL_CTL_MOD, fdVal, (event | EPOLLONESHOT));
        if (err == ENOENT)
            err = EPoll.ctl(epfd, EPOLL_CTL_ADD, fdVal, (event | EPOLLONESHOT));
        if (err != 0)
            throw new IOException("epoll_ctl failed: " + err);
    }

    @Override
    void implDeregister(int fdVal) {
        EPoll.ctl(epfd, EPOLL_CTL_DEL, fdVal, 0);
    }

    @Override
    int poll(int timeout) throws IOException {
        int n = EPoll.wait(epfd, address, MAX_EVENTS_TO_POLL, timeout);
        int i = 0;
        while (i < n) {
            long eventAddress = EPoll.getEvent(address, i);
            int fdVal = EPoll.getDescriptor(eventAddress);
            polled(fdVal);
            i++;
        }
        return n;
    }
}

