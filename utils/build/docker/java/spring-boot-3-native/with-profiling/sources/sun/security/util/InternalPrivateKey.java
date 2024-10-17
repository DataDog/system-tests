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
package sun.security.util;

import java.security.PublicKey;

/**
 * Extra private methods on a private key.
 */
public interface InternalPrivateKey {
    /**
     * Calculates a matching public key.
     * @return the public key
     * @throws UnsupportedOperationException if not supported
     */
    default PublicKey calculatePublicKey() {
        throw new UnsupportedOperationException();
    }
}
