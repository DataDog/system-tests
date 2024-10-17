/*
 * Copyright (c) 2008, 2021, Oracle and/or its affiliates. All rights reserved.
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

import java.nio.charset.Charset;
import java.security.AccessController;
import java.security.PrivilegedAction;
import sun.net.NetProperties;
import jdk.internal.util.StaticProperty;

/**
 * Platform specific utility functions
 */
class UnixDomainSocketsUtil {
    private UnixDomainSocketsUtil() { }

    static Charset getCharset() {
        return Charset.defaultCharset();
    }

    /**
     * Return the temp directory for storing automatically bound
     * server sockets.
     *
     * On UNIX we search the following directories in sequence:
     *
     * 1. ${jdk.net.unixdomain.tmpdir} if set as system property
     * 2. ${jdk.net.unixdomain.tmpdir} if set as net property
     * 3. ${java.io.tmpdir} system property
     */
    @SuppressWarnings("removal")
    static String getTempDir() {
        PrivilegedAction<String> action = () -> {
            String s = NetProperties.get("jdk.net.unixdomain.tmpdir");
            if (s != null && s.length() > 0) {
                return s;
            } else {
                return StaticProperty.javaIoTmpDir();
            }
        };
        return AccessController.doPrivileged(action);
    }
}
