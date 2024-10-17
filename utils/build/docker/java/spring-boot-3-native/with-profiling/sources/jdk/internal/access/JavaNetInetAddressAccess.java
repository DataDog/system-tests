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

package jdk.internal.access;

import java.net.Inet4Address;
import java.net.Inet6Address;
import java.net.InetAddress;

public interface JavaNetInetAddressAccess {
    /**
     * Return the original application specified hostname of
     * the given InetAddress object.
     */
    String getOriginalHostName(InetAddress ia);

    /**
     * Returns the 32-bit IPv4 address.
     */
    int addressValue(Inet4Address inet4Address);

    /**
     * Returns a reference to the byte[] with the IPv6 address.
     */
    byte[] addressBytes(Inet6Address inet6Address);
}
