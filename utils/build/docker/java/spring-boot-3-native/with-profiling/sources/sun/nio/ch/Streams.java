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

import java.io.InputStream;
import java.io.OutputStream;
import java.nio.channels.ReadableByteChannel;
import java.nio.channels.WritableByteChannel;

/**
 * Factory methods for input/output streams based on channels.
 */
public class Streams {
    private Streams() { }

    /**
     * Return an input stream that reads bytes from the given channel.
     */
    public static InputStream of(ReadableByteChannel ch) {
        if (ch instanceof SocketChannelImpl sc) {
            return new SocketInputStream(sc);
        } else {
            return new ChannelInputStream(ch);
        }
    }

    /**
     * Return an output stream that writes bytes to the given channel.
     */
    public static OutputStream of(WritableByteChannel ch) {
        if (ch instanceof SocketChannelImpl sc) {
            return new SocketOutputStream(sc);
        } else {
            return new ChannelOutputStream(ch);
        }
    }
}
