/*
 * Copyright (c) 2015, 2021, Oracle and/or its affiliates. All rights reserved.
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

package sun.nio.ch;

import java.security.AccessController;
import java.security.PrivilegedAction;

/**
 * Creates this platform's default SelectorProvider
 */

@SuppressWarnings("removal")
public class DefaultSelectorProvider {
    private static final SelectorProviderImpl INSTANCE;
    static {
        PrivilegedAction<SelectorProviderImpl> pa = EPollSelectorProvider::new;
        INSTANCE = AccessController.doPrivileged(pa);
    }

    /**
     * Prevent instantiation.
     */
    private DefaultSelectorProvider() { }

    /**
     * Returns the default SelectorProvider implementation.
     */
    public static SelectorProviderImpl get() {
        return INSTANCE;
    }
}
