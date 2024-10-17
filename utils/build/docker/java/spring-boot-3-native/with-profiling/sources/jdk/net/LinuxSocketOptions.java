/*
 * Copyright (c) 2017, 2021, Oracle and/or its affiliates. All rights reserved.
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
package jdk.net;

import java.net.SocketException;
import java.nio.file.attribute.UserPrincipal;
import java.nio.file.attribute.GroupPrincipal;
import java.security.AccessController;
import java.security.PrivilegedAction;
import jdk.net.ExtendedSocketOptions.PlatformSocketOptions;
import sun.nio.fs.UnixUserPrincipals;

@SuppressWarnings("removal")
class LinuxSocketOptions extends PlatformSocketOptions {

    public LinuxSocketOptions() {
    }

    @Override
    void setQuickAck(int fd, boolean on) throws SocketException {
        setQuickAck0(fd, on);
    }

    @Override
    boolean getQuickAck(int fd) throws SocketException {
        return getQuickAck0(fd);
    }

    @Override
    public boolean quickAckSupported() {
        return quickAckSupported0();
    }

    @Override
    boolean keepAliveOptionsSupported() {
        return keepAliveOptionsSupported0();
    }

    @Override
    boolean ipDontFragmentSupported() {
        return true;
    }

    boolean peerCredentialsSupported() {
        return true;
    }

    @Override
    void setTcpKeepAliveProbes(int fd, final int value) throws SocketException {
        setTcpKeepAliveProbes0(fd, value);
    }

    @Override
    void setTcpKeepAliveTime(int fd, final int value) throws SocketException {
        setTcpKeepAliveTime0(fd, value);
    }

    @Override
    void setTcpKeepAliveIntvl(int fd, final int value) throws SocketException {
        setTcpKeepAliveIntvl0(fd, value);
    }

    @Override
    int getTcpKeepAliveProbes(int fd) throws SocketException {
        return getTcpKeepAliveProbes0(fd);
    }

    @Override
    int getTcpKeepAliveTime(int fd) throws SocketException {
        return getTcpKeepAliveTime0(fd);
    }

    @Override
    int getTcpKeepAliveIntvl(int fd) throws SocketException {
        return getTcpKeepAliveIntvl0(fd);
    }

    @Override
    boolean incomingNapiIdSupported() {
        return incomingNapiIdSupported0();
    }

    @Override
    int getIncomingNapiId(int fd) throws SocketException {
        return getIncomingNapiId0(fd);
    }

    @Override
    void setIpDontFragment(int fd, final boolean value, boolean isIPv6) throws SocketException {
        setIpDontFragment0(fd, value, isIPv6);
    }

    @Override
    boolean getIpDontFragment(int fd, boolean isIPv6) throws SocketException {
        return getIpDontFragment0(fd, isIPv6);
    }

    @Override
    UnixDomainPrincipal getSoPeerCred(int fd) throws SocketException {
        long l = getSoPeerCred0(fd);
        int uid = (int)(l >> 32);
        int gid = (int)l;
        UserPrincipal user = UnixUserPrincipals.fromUid(uid);
        GroupPrincipal group = UnixUserPrincipals.fromGid(gid);
        return new UnixDomainPrincipal(user, group);
    }

    private static native void setTcpKeepAliveProbes0(int fd, int value) throws SocketException;
    private static native void setTcpKeepAliveTime0(int fd, int value) throws SocketException;
    private static native void setTcpKeepAliveIntvl0(int fd, int value) throws SocketException;
    private static native void setIpDontFragment0(int fd, boolean value, boolean isIPv6) throws SocketException;
    private static native int getTcpKeepAliveProbes0(int fd) throws SocketException;
    private static native int getTcpKeepAliveTime0(int fd) throws SocketException;
    private static native int getTcpKeepAliveIntvl0(int fd) throws SocketException;
    private static native boolean getIpDontFragment0(int fd, boolean isIPv6) throws SocketException;
    private static native void setQuickAck0(int fd, boolean on) throws SocketException;
    private static native boolean getQuickAck0(int fd) throws SocketException;
    private static native long getSoPeerCred0(int fd) throws SocketException;
    private static native boolean keepAliveOptionsSupported0();
    private static native boolean quickAckSupported0();
    private static native boolean incomingNapiIdSupported0();
    private static native int getIncomingNapiId0(int fd) throws SocketException;
    static {
        if (System.getSecurityManager() == null) {
            System.loadLibrary("extnet");
        } else {
            AccessController.doPrivileged((PrivilegedAction<Void>) () -> {
                System.loadLibrary("extnet");
                return null;
            });
        }
    }
}

