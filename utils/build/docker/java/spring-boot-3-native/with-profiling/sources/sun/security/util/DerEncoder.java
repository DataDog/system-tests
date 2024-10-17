/*
 * Copyright (c) 1997, 2022, Oracle and/or its affiliates. All rights reserved.
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

package sun.security.util;

/**
 * Interface to an object that knows how to write its own DER
 * encoding to an output stream.
 *
 * @author D. N. Hoover
 */
public interface DerEncoder {

    /**
     * DER encode this object and write the results to a stream.
     *
     * @param out  the stream on which the DER encoding is written.
     */
    void encode(DerOutputStream out);

}
