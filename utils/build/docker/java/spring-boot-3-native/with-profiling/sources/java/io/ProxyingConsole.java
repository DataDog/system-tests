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

package java.io;

import java.nio.charset.Charset;
import jdk.internal.io.JdkConsole;

/**
 * Console implementation for internal use. Custom Console delegate may be
 * provided with jdk.internal.io.JdkConsoleProvider.
 */
final class ProxyingConsole extends Console {
    private final JdkConsole delegate;
    private final Object readLock;
    private final Object writeLock;
    private final Reader reader;
    private final PrintWriter printWriter;

    ProxyingConsole(JdkConsole delegate) {
        this.delegate = delegate;
        readLock = new Object();
        writeLock = new Object();
        reader = new WrappingReader(delegate.reader(), readLock);
        printWriter = new WrappingWriter(delegate.writer(), writeLock);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public PrintWriter writer() {
        return printWriter;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public Reader reader() {
        return reader;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public Console format(String fmt, Object ... args) {
        synchronized (writeLock) {
            delegate.format(fmt, args);
        }
        return this;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public Console printf(String format, Object ... args) {
        synchronized (writeLock) {
            delegate.printf(format, args);
        }
        return this;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public String readLine(String fmt, Object ... args) {
        synchronized (writeLock) {
            synchronized (readLock) {
                return delegate.readLine(fmt, args);
            }
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public String readLine() {
        synchronized (readLock) {
            return delegate.readLine();
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public char[] readPassword(String fmt, Object ... args) {
        synchronized (writeLock) {
            synchronized (readLock) {
                return delegate.readPassword(fmt, args);
            }
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public char[] readPassword() {
        synchronized (readLock) {
            return delegate.readPassword();
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void flush() {
        delegate.flush();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public Charset charset() {
        return delegate.charset();
    }

    private static final class WrappingReader extends Reader {
        private final Reader r;
        private final Object lock;

        WrappingReader(Reader r, Object lock) {
            super(lock);
            this.r = r;
            this.lock = lock;
        }

        @Override
        public int read(char[] cbuf, int off, int len) throws IOException {
            synchronized (lock) {
                return r.read(cbuf, off, len);
            }
        }

        @Override
        public void close() {
            // no-op, per Console's spec
        }
    }

    private static final class WrappingWriter extends PrintWriter {
        private final PrintWriter pw;
        private final Object lock;

        public WrappingWriter(PrintWriter pw, Object lock) {
            super(pw, lock);
            this.pw = pw;
            this.lock = lock;
        }

        @Override
        public void write(char[] cbuf, int off, int len) {
            synchronized (lock) {
                pw.write(cbuf, off, len);
            }
        }

        @Override
        public void flush() {
            pw.flush();
        }

        @Override
        public void close() {
            // no-op, per Console's spec
        }
    }
}
