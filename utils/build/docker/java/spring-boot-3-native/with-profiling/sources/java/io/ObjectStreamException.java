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

package java.io;

/**
 * Superclass of all exceptions specific to Object Stream classes.
 *
 * @since   1.1
 */
public abstract class ObjectStreamException extends IOException {

    @java.io.Serial
    private static final long serialVersionUID = 7260898174833392607L;

    /**
     * Create an ObjectStreamException with the specified argument.
     *
     * @param message the detailed message for the exception
     */
    protected ObjectStreamException(String message) {
        super(message);
    }

    /**
     * Create an ObjectStreamException with the specified message and
     * cause.
     *
     * @param message the detailed message for the exception
     * @param cause the cause
     * @since 19
     */
    protected ObjectStreamException(String message, Throwable cause) {
        super(message, cause);
    }

    /**
     * Create an ObjectStreamException.
     */
    protected ObjectStreamException() {
        super();
    }

    /**
     * Create an ObjectStreamException with the specified cause.
     *
     * @param cause the cause
     * @since 19
     */
    protected ObjectStreamException(Throwable cause) {
        super(cause);
    }
}
