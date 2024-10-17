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

package java.lang;

/**
 * Thrown to indicate that a method has been called on the wrong thread.
 *
 * @since 19
 */
public final class WrongThreadException extends RuntimeException {
    @java.io.Serial
    static final long serialVersionUID = 4676498871006316905L;

    /**
     * Constructs a WrongThreadException with no detail message.
     */
    public WrongThreadException() {
        super();
    }

    /**
     * Constructs a WrongThreadException with the given detail message.
     *
     * @param s the String that contains a detailed message, can be null
     */
    public WrongThreadException(String s) {
        super(s);
    }

    /**
     * Constructs a WrongThreadException with the given detail message and cause.
     *
     * @param  message the detail message, can be null
     * @param  cause the cause, can be null
     */
    public WrongThreadException(String message, Throwable cause) {
        super(message, cause);
    }

    /**
     * Constructs a WrongThreadException with the given cause and a detail
     * message of {@code (cause==null ? null : cause.toString())} (which
     * typically contains the class and detail message of {@code cause}).
     *
     * @param  cause the cause, can be null
     */
    public WrongThreadException(Throwable cause) {
        super(cause);
    }
}
