/*
 * Copyright (c) 2009, 2022, Oracle and/or its affiliates. All rights reserved.
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

package sun.security.jgss;

/**
 * Denotes what client is calling the JGSS-API. The object can be sent deep
 * into the mechanism level so that special actions can be performed for
 * different callers.
 */
public sealed class GSSCaller permits HttpCaller {

    public static final GSSCaller CALLER_UNKNOWN = new GSSCaller("UNKNOWN");
    public static final GSSCaller CALLER_INITIATE = new GSSCaller("INITIATE");
    public static final GSSCaller CALLER_ACCEPT = new GSSCaller("ACCEPT");

    private final String name;
    GSSCaller(String s) {
        name = s;
    }
    @Override
    public String toString() {
        return "GSSCaller{" + name + '}';
    }
}

