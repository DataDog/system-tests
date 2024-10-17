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

package sun.security.util;

import java.math.BigInteger;
import javax.crypto.spec.DHParameterSpec;

/**
 * Internal marker class for well-known safe DH parameters. It should
 * only be used with trusted callers since it does not have all the needed
 * values for validation.
 */

public final class SafeDHParameterSpec extends DHParameterSpec {
    public SafeDHParameterSpec(BigInteger p, BigInteger g) {
        super(p, g);
    }

    public SafeDHParameterSpec(BigInteger p, BigInteger g, int l) {
        super(p, g, l);
    }
}
