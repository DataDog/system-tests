/*
 * Copyright (c) 2018, 2024, Oracle and/or its affiliates. All rights reserved.
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

package jdk.internal.event;

import jdk.internal.access.JavaUtilJarAccess;
import jdk.internal.access.SharedSecrets;
import jdk.internal.misc.ThreadTracker;

import java.lang.invoke.MethodHandles;
import java.lang.invoke.VarHandle;
import java.time.Duration;
import java.time.Instant;
import java.util.Date;
import java.util.stream.Collectors;
import java.util.stream.LongStream;

/**
 * A helper class to have events logged to a JDK Event Logger.
 */

public final class EventHelper {

    private static final JavaUtilJarAccess JUJA = SharedSecrets.javaUtilJarAccess();
    private static volatile boolean loggingSecurity;
    private static volatile System.Logger securityLogger;
    private static final VarHandle LOGGER_HANDLE;
    static {
        try {
            LOGGER_HANDLE =
                    MethodHandles.lookup().findStaticVarHandle(
                            EventHelper.class, "securityLogger", System.Logger.class);
        } catch (ReflectiveOperationException e) {
            throw new Error(e);
        }
    }
    private static final System.Logger.Level LOG_LEVEL = System.Logger.Level.DEBUG;

    // helper class used for logging security related events for now
    private static final String SECURITY_LOGGER_NAME = "jdk.event.security";


    public static void logTLSHandshakeEvent(Instant start,
                                            String peerHost,
                                            int peerPort,
                                            String cipherSuite,
                                            String protocolVersion,
                                            long peerCertId) {
        assert securityLogger != null;
        String prepend = getDurationString(start);
        securityLogger.log(LOG_LEVEL, prepend +
        " TLSHandshake: {0}:{1,number,#}, {2}, {3}, {4,number,#}",
        peerHost, peerPort, protocolVersion, cipherSuite, peerCertId);
    }

    public static void logSecurityPropertyEvent(String key,
                                                String value) {

        assert securityLogger != null;
        securityLogger.log(LOG_LEVEL,
            "SecurityPropertyModification: key:{0}, value:{1}", key, value);
    }

    public static void logX509ValidationEvent(long anchorCertId,
                                         long[] certIds) {
        assert securityLogger != null;
        String codes = LongStream.of(certIds)
                .mapToObj(Long::toString)
                .collect(Collectors.joining(", "));
        securityLogger.log(LOG_LEVEL,
                "ValidationChain: {0,number,#}, {1}", anchorCertId, codes);
    }

    public static void logX509CertificateEvent(String algId,
                                               String serialNum,
                                               String subject,
                                               String issuer,
                                               String keyType,
                                               int length,
                                               long certId,
                                               long beginDate,
                                               long endDate) {
        assert securityLogger != null;
        securityLogger.log(LOG_LEVEL, "X509Certificate: Alg:{0}, Serial:{1}" +
            ", Subject:{2}, Issuer:{3}, Key type:{4}, Length:{5,number,#}" +
            ", Cert Id:{6,number,#}, Valid from:{7}, Valid until:{8}",
            algId, serialNum, subject, issuer, keyType, length,
            certId, new Date(beginDate), new Date(endDate));
    }

    /**
     * Method to calculate a duration timestamp for events which measure
     * the start and end times of certain operations.
     * @param start Instant indicating when event started recording
     * @return A string representing duraction from start time to
     * time of this method call. Empty string is start is null.
     */
    private static String getDurationString(Instant start) {
        if (start != null) {
            if (start.equals(Instant.MIN)) {
                return "N/A";
            }
            Duration duration = Duration.between(start, Instant.now());
            long micros = duration.toNanos() / 1_000;
            if (micros < 1_000_000) {
                return "duration = " + (micros / 1_000.0) + " ms:";
            } else {
                return "duration = " + ((micros / 1_000) / 1_000.0) + " s:";
            }
        } else {
            return "";
        }
    }

    private static class ThreadTrackHolder {
        static final ThreadTracker TRACKER = new ThreadTracker();
    }

    private static Object tryBeginLookup() {
        return ThreadTrackHolder.TRACKER.tryBegin();
    }

    private static void endLookup(Object key) {
        ThreadTrackHolder.TRACKER.end(key);
    }

    /**
     * Helper to determine if security events are being logged
     * at a preconfigured logging level. The configuration value
     * is read once at class initialization.
     *
     * @return boolean indicating whether an event should be logged
     */
    public static boolean isLoggingSecurity() {
        Object key;
        // Avoid bootstrap issues where
        // * commitEvent triggers early loading of System Logger but where
        //   the verification process still has JarFiles locked
        // * the loading of the logging libraries involves recursive
        //   calls to security libraries triggering recursion
        if (securityLogger == null && !JUJA.isInitializing() && (key = tryBeginLookup()) != null) {
            try {
                LOGGER_HANDLE.compareAndSet(null, System.getLogger(SECURITY_LOGGER_NAME));
                loggingSecurity = securityLogger.isLoggable(LOG_LEVEL);
            } finally {
                endLookup(key);
            }
        }
        return loggingSecurity;
    }
}
