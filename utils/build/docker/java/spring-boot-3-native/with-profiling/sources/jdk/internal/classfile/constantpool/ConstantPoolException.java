/*
 * Copyright (c) 2023, Oracle and/or its affiliates. All rights reserved.
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
package jdk.internal.classfile.constantpool;

/**
 * Thrown to indicate that requested entry cannot be obtained from the constant
 * pool.
 */
public class ConstantPoolException extends IllegalArgumentException {

    @java.io.Serial
    private static final long serialVersionUID = 7245472922409094120L;

    /**
     * Constructs a {@code ConstantPoolException} with no detail message.
     */
    public ConstantPoolException() {
        super();
    }

    /**
     * Constructs a {@code ConstantPoolException} with the specified detail
     * message.
     *
     * @param message the detail message.
     */
    public ConstantPoolException(String message) {
        super(message);
    }

    /**
     * Constructs a {@code ConstantPoolException} with the specified cause and
     * a detail message of {@code (cause==null ? null : cause.toString())}.
     * @param cause the cause (which is saved for later retrieval by the
     *        {@link Throwable#getCause()} method).  (A {@code null} value is
     *        permitted, and indicates that the cause is nonexistent or
     *        unknown.)
     */
    public ConstantPoolException(Throwable cause) {
        super(cause);
    }

    /**
     * Constructs a {@code ConstantPoolException} with the specified detail
     * message and cause.
     *
     * @param message the detail message (which is saved for later retrieval
     *        by the {@link Throwable#getMessage()} method).
     * @param cause the cause (which is saved for later retrieval by the
     *        {@link Throwable#getCause()} method).  (A {@code null} value
     *        is permitted, and indicates that the cause is nonexistent or
     *        unknown.)
     */
    public ConstantPoolException(String message, Throwable cause) {
        super(message, cause);
    }
}
