/*
 * Copyright (c) 2009, 2016, Oracle and/or its affiliates. All rights reserved.
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

package sun.net.www.protocol.http;

import java.net.Authenticator;
import java.net.Authenticator.RequestorType;
import java.net.InetAddress;
import java.net.URL;
import java.security.cert.X509Certificate;

/**
 * Used in HTTP/Negotiate, to feed HTTP request info into JGSS as a HttpCaller,
 * so that special actions can be taken, including special callback handler,
 * special useSubjectCredsOnly value.
 *
 * This is an immutable class. It can be instantiated in two styles;
 *
 * 1. Un-schemed: Create at the beginning before the preferred scheme is
 * determined. This object can be fed into AuthenticationHeader to check
 * for the preference.
 *
 * 2. Schemed: With the scheme field filled, can be used in JGSS-API calls.
 */
public final class HttpCallerInfo {
    // All info that an Authenticator needs.
    public final URL url;
    public final String host, protocol, prompt, scheme;
    public final int port;
    public final InetAddress addr;
    public final RequestorType authType;
    public final Authenticator authenticator;
    // Used to obtain server cert for SPNEGO CBT.
    // May be null in which case CBT is not set
    public final X509Certificate serverCert;

    /**
     * Create a schemed object based on an un-schemed one.
     */
    public HttpCallerInfo(HttpCallerInfo old, String scheme) {
        this.url = old.url;
        this.host = old.host;
        this.protocol = old.protocol;
        this.prompt = old.prompt;
        this.port = old.port;
        this.addr = old.addr;
        this.authType = old.authType;
        this.scheme = scheme;
        this.authenticator =  old.authenticator;
        this.serverCert =  old.serverCert;
    }

    /**
     * Constructor an un-schemed object for site access.
     */
    public HttpCallerInfo(URL url, Authenticator a) {
        this(url, null, a);
    }

    public HttpCallerInfo(URL url, X509Certificate serverCert, Authenticator a) {
        this.url= url;
        this.serverCert= serverCert;
        prompt = "";
        host = url.getHost();

        int p = url.getPort();
        if (p == -1) {
            port = url.getDefaultPort();
        } else {
            port = p;
        }

        InetAddress ia;
        try {
            ia = InetAddress.getByName(url.getHost());
        } catch (Exception e) {
            ia = null;
        }
        addr = ia;

        protocol = url.getProtocol();
        authType = RequestorType.SERVER;
        scheme = "";
        authenticator = a;
    }

    /**
     * Constructor an un-schemed object for proxy access.
     */
    public HttpCallerInfo(URL url, String host, int port, Authenticator a) {
        this(url, host, port, null, a);
    }

    public HttpCallerInfo(URL url, String host, int port, X509Certificate serverCert, Authenticator a) {
        this.url= url;
        this.host = host;
        this.port = port;
        this.serverCert = serverCert;
        prompt = "";
        addr = null;
        protocol = url.getProtocol();
        authType = RequestorType.PROXY;
        scheme = "";
        authenticator = a;
    }
}
