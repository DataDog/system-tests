/*
 * Copyright (c) 1996, 2022, Oracle and/or its affiliates. All rights reserved.
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

package java.security;

/**
 * This exception, designed for use by the JCA/JCE engine classes,
 * is thrown when an invalid parameter is passed
 * to a method.
 *
 * @author Benjamin Renaud
 * @since 1.1
 */

public class InvalidParameterException extends IllegalArgumentException {

    @java.io.Serial
    private static final long serialVersionUID = -857968536935667808L;

    /**
     * Constructs an {@code InvalidParameterException} with no detail message.
     * A detail message is a {@code String} that describes this particular
     * exception.
     */
    public InvalidParameterException() {
        super();
    }

    /**
     * Constructs an {@code InvalidParameterException} with the specified
     * detail message.  A detail message is a {@code String} that describes
     * this particular exception.
     *
     * @param msg the detail message.
     */
    public InvalidParameterException(String msg) {
        super(msg);
    }

    /**
     * Constructs an {@code InvalidParameterException} with the specified
     * detail message and cause. A detail message is a {@code String}
     * that describes this particular exception.
     *
     * <p>Note that the detail message associated with {@code cause} is
     * <i>not</i> automatically incorporated in this exception's detail
     * message.
     *
     * @param  msg the detail message (which is saved for later retrieval
     *         by the {@link Throwable#getMessage()} method).
     * @param  cause the cause (which is saved for later retrieval by the
     *         {@link Throwable#getCause()} method). (A {@code null} value
     *         is permitted, and indicates that the cause is nonexistent or
     *         unknown.)
     *
     * @since  20
     */
    public InvalidParameterException(String msg, Throwable cause) {
        super(msg, cause);
    }

    /**
     * Constructs an {@code InvalidParameterException} with the specified cause
     * and a detail message of {@code (cause==null ? null : cause.toString())}
     * (which typically contains the class and detail message of {@code cause}).
     * This constructor is useful for exceptions that are little more than
     * wrappers for other throwables.
     *
     * @param  cause the cause (which is saved for later retrieval by the
     *         {@link Throwable#getCause()} method). (A {@code null} value is
     *         permitted, and indicates that the cause is nonexistent or
     *         unknown.)
     *
     * @since  20
     */
    public InvalidParameterException(Throwable cause) {
        super(cause);
    }
}
