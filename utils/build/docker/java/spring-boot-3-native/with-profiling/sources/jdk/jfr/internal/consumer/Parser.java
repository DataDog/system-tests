/*
 * Copyright (c) 2016, 2022, Oracle and/or its affiliates. All rights reserved.
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

package jdk.jfr.internal.consumer;

import java.io.IOException;

/**
 * Base class for parsing data from a {@link RecordingInput}.
 */
abstract class Parser {
    /**
     * Parses data from a {@link RecordingInput} and return an object.
     *
     * @param input input to read from
     * @return an {@code Object}, an {@code Object[]}, or {@code null}
     * @throws IOException if operation couldn't be completed due to I/O
     *         problems
     */
    public abstract Object parse(RecordingInput input) throws IOException;

    /**
     * Parses data from a {@link RecordingInput} to find references to constants. If
     * data is not a reference, {@code null} is returned.
     * <p>
     * @implSpec The default implementation of this method skips data and returns
     * {@code Object}.
     *
     * @param input input to read from, not {@code null}
     * @return a {@code Reference}, a {@code Reference[]}, or {@code null}
     * @throws IOException if operation couldn't be completed due to I/O problems
     */
    public Object parseReferences(RecordingInput input) throws IOException {
        skip(input);
        return null;
    }

    /**
     * Skips data that would usually be by parsed the {@link #parse(RecordingInput)} method.
     *
     * @param input input to read from
     * @throws IOException if operation couldn't be completed due to I/O
     *         problems
     */
    public abstract void skip(RecordingInput input) throws IOException;
}
