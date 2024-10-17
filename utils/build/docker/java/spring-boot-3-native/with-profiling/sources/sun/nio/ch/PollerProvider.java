/*
 * Copyright (c) 2017, 2022, Oracle and/or its affiliates. All rights reserved.
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

import java.io.IOException;
import java.util.ServiceConfigurationError;
import sun.security.action.GetPropertyAction;

abstract class PollerProvider {
    PollerProvider() { }

    /**
     * Returns true if threads should register file descriptors directly,
     * false to queue registrations to an updater thread.
     *
     * The default implementation returns false.
     */
    boolean useDirectRegister() {
        return false;
    }

    /**
     * Creates a Poller for read ops.
     */
    abstract Poller readPoller() throws IOException;

    /**
     * Creates a Poller for write ops.
     */
    abstract Poller writePoller() throws IOException;

    /**
     * Creates the PollerProvider.
     */
    static PollerProvider provider() {
        String cn = GetPropertyAction.privilegedGetProperty("jdk.PollerProvider");
        if (cn != null) {
            try {
                Class<?> clazz = Class.forName(cn, true, ClassLoader.getSystemClassLoader());
                return (PollerProvider) clazz.getConstructor().newInstance();
            } catch (Exception e) {
                throw new ServiceConfigurationError(null, e);
            }
        } else {
            return new DefaultPollerProvider();
        }
    }
}
