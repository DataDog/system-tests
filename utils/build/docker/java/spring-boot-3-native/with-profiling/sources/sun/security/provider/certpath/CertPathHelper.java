/*
 * Copyright (c) 2002, 2023, Oracle and/or its affiliates. All rights reserved.
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

package sun.security.provider.certpath;

import java.util.Date;

import java.security.cert.TrustAnchor;
import java.security.cert.X509CRLSelector;

/**
 * Helper class that allows access to JDK specific known-public methods in the
 * java.security.cert package. It relies on a subclass in the
 * java.security.cert packages that is initialized before any of these methods
 * are called (achieved via static initializers).
 *
 * The methods are made available in this fashion for performance reasons.
 *
 * @author Andreas Sterbenz
 */
public abstract class CertPathHelper {

    /**
     * Object used to tunnel the calls. Initialized by CertPathHelperImpl.
     */
    protected static CertPathHelper instance;

    protected CertPathHelper() {
        // empty
    }

    protected abstract void implSetDateAndTime(X509CRLSelector sel, Date date, long skew);

    protected abstract boolean implIsJdkCA(TrustAnchor anchor);

    public static void setDateAndTime(X509CRLSelector sel, Date date, long skew) {
        instance.implSetDateAndTime(sel, date, skew);
    }

    public static boolean isJdkCA(TrustAnchor anchor) {
        return anchor != null && instance.implIsJdkCA(anchor);
    }
}
