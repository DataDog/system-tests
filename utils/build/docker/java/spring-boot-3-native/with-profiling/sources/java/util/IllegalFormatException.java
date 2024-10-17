/*
 * Copyright (c) 2003, 2022, Oracle and/or its affiliates. All rights reserved.
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

package java.util;

/**
 * Unchecked exception thrown when a format string contains an illegal syntax
 * or a format specifier that is incompatible with the given arguments.  Only
 * explicit subtypes of this exception which correspond to specific errors
 * should be instantiated.
 *
 * @since 1.5
 */
public sealed class IllegalFormatException extends IllegalArgumentException
    permits DuplicateFormatFlagsException,
            FormatFlagsConversionMismatchException,
            IllegalFormatArgumentIndexException,
            IllegalFormatCodePointException,
            IllegalFormatConversionException,
            IllegalFormatFlagsException,
            IllegalFormatPrecisionException,
            IllegalFormatWidthException,
            MissingFormatArgumentException,
            MissingFormatWidthException,
            UnknownFormatConversionException,
            UnknownFormatFlagsException {

    @java.io.Serial
    private static final long serialVersionUID = 18830826L;

    // package-private to prevent explicit instantiation
    IllegalFormatException() { }
}
