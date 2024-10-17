/*
 * Copyright (c) 2003, 2022, Oracle and/or its affiliates. All rights reserved.
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

package sun.security.jca;

import java.security.PublicKey;
import java.security.SecureRandom;
import java.security.cert.Certificate;
import java.security.cert.X509Certificate;

import jdk.internal.event.EventHelper;
import jdk.internal.event.X509CertificateEvent;
import sun.security.util.KeyUtil;

/**
 * Collection of static utility methods used by the security framework.
 *
 * @author  Andreas Sterbenz
 * @since   1.5
 */
public final class JCAUtil {

    private JCAUtil() {
        // no instantiation
    }

    // size of the temporary arrays we use. Should fit into the CPU's 1st
    // level cache and could be adjusted based on the platform
    private static final int ARRAY_SIZE = 4096;

    /**
     * Get the size of a temporary buffer array to use in order to be
     * cache efficient. totalSize indicates the total amount of data to
     * be buffered. Used by the engineUpdate(ByteBuffer) methods.
     */
    public static int getTempArraySize(int totalSize) {
        return Math.min(ARRAY_SIZE, totalSize);
    }

    // cached SecureRandom instance
    private static class CachedSecureRandomHolder {
        public static SecureRandom instance = new SecureRandom();
    }

    private static volatile SecureRandom def = null;

    /**
     * Get a SecureRandom instance. This method should be used by JDK
     * internal code in favor of calling "new SecureRandom()". That needs to
     * iterate through the provider table to find the default SecureRandom
     * implementation, which is fairly inefficient.
     */
    public static SecureRandom getSecureRandom() {
        return CachedSecureRandomHolder.instance;
    }

    // called by sun.security.jca.Providers class when provider list is changed
    static void clearDefSecureRandom() {
        def = null;
    }

    /**
     * Get the default SecureRandom instance. This method is the
     * optimized version of "new SecureRandom()" which re-uses the default
     * SecureRandom impl if the provider table is the same.
     */
    public static SecureRandom getDefSecureRandom() {
        SecureRandom result = def;
        if (result == null) {
            synchronized (JCAUtil.class) {
                result = def;
                if (result == null) {
                    def = result = new SecureRandom();
                }
            }
        }
        return result;
    }

    public static void tryCommitCertEvent(Certificate cert) {
        if ((X509CertificateEvent.isTurnedOn() || EventHelper.isLoggingSecurity()) &&
                (cert instanceof X509Certificate x509)) {
            PublicKey pKey = x509.getPublicKey();
            String algId = x509.getSigAlgName();
            String serNum = x509.getSerialNumber().toString(16);
            String subject = x509.getSubjectX500Principal().toString();
            String issuer = x509.getIssuerX500Principal().toString();
            String keyType = pKey.getAlgorithm();
            int length = KeyUtil.getKeySize(pKey);
            int hashCode = x509.hashCode();
            long certifcateId = Integer.toUnsignedLong(hashCode);
            long beginDate = x509.getNotBefore().getTime();
            long endDate = x509.getNotAfter().getTime();
            if (X509CertificateEvent.isTurnedOn()) {
                X509CertificateEvent xce = new X509CertificateEvent();
                xce.algorithm = algId;
                xce.serialNumber = serNum;
                xce.subject = subject;
                xce.issuer = issuer;
                xce.keyType = keyType;
                xce.keyLength = length;
                xce.certificateId = certifcateId;
                xce.validFrom = beginDate;
                xce.validUntil = endDate;
                xce.commit();
            }
            if (EventHelper.isLoggingSecurity()) {
                EventHelper.logX509CertificateEvent(algId,
                        serNum,
                        subject,
                        issuer,
                        keyType,
                        length,
                        certifcateId,
                        beginDate,
                        endDate);
            }
        }
    }
}
