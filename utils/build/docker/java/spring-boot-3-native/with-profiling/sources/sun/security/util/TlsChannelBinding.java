/*
 * Copyright (c) 2022, Azul Systems, Inc. All rights reserved.
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

package sun.security.util;

import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.cert.CertificateEncodingException;
import java.security.cert.X509Certificate;
import java.util.Arrays;
import java.util.Locale;

/**
 * This class implements the Channel Binding for TLS as defined in
 * <a href="https://www.ietf.org/rfc/rfc5929.txt">
 *     Channel Bindings for TLS</a>
 *
 * Format of the Channel Binding data is also defined in
 * <a href="https://www.ietf.org/rfc/rfc5056.txt">
 *     On the Use of Channel Bindings to Secure Channels</a>
 * section 2.1.
 *
 */

public class TlsChannelBinding {

    public enum TlsChannelBindingType {

        /**
         * Channel binding on the basis of TLS Finished message.
         * TLS_UNIQUE is defined by RFC 5929 but is not supported
         * by the current LDAP stack.
         */
        TLS_UNIQUE("tls-unique"),

        /**
         * Channel binding on the basis of TLS server certificate.
         */
        TLS_SERVER_END_POINT("tls-server-end-point");

        public String getName() {
            return name;
        }

        private final String name;
        TlsChannelBindingType(String name) {
            this.name = name;
        }
    }

    /**
     * Parse given value to see if it is a recognized and supported channel binding type
     *
     * @param  cbType
     * @return TLS Channel Binding type or null if given string is null
     * @throws ChannelBindingException
     */
    public static TlsChannelBindingType parseType(String cbType) throws ChannelBindingException {
        if (cbType != null) {
            if (cbType.equals(TlsChannelBindingType.TLS_SERVER_END_POINT.getName())) {
                return TlsChannelBindingType.TLS_SERVER_END_POINT;
            } else {
                throw new ChannelBindingException("Illegal value for channel binding type: " + cbType);
            }
        }
        return null;
    }

    private final TlsChannelBindingType cbType;
    private final byte[] cbData;

    /**
     * Construct tls-server-end-point Channel Binding data
     * @param serverCertificate
     * @throws ChannelBindingException
     */
    public static TlsChannelBinding create(X509Certificate serverCertificate) throws ChannelBindingException {
        try {
            final byte[] prefix =
                TlsChannelBindingType.TLS_SERVER_END_POINT.getName().concat(":").getBytes();
            String hashAlg = serverCertificate.getSigAlgName().
                    toUpperCase(Locale.ENGLISH).replace("SHA", "SHA-");
            int ind = hashAlg.indexOf("WITH");
            if (ind > 0) {
                hashAlg = hashAlg.substring(0, ind);
                if (hashAlg.equals("MD5") || hashAlg.equals("SHA-1")) {
                    hashAlg = "SHA-256";
                }
            } else {
                hashAlg = "SHA-256";
            }
            MessageDigest md = MessageDigest.getInstance(hashAlg);
            byte[] hash = md.digest(serverCertificate.getEncoded());
            byte[] cbData = Arrays.copyOf(prefix, prefix.length + hash.length );
            System.arraycopy(hash, 0, cbData, prefix.length, hash.length);
            return new TlsChannelBinding(TlsChannelBindingType.TLS_SERVER_END_POINT, cbData);
        } catch (NoSuchAlgorithmException | CertificateEncodingException e) {
            throw new ChannelBindingException("Cannot create TLS channel binding data", e);
        }
    }

    private TlsChannelBinding(TlsChannelBindingType cbType, byte[] cbData) {
        this.cbType = cbType;
        this.cbData = cbData;
    }

    public TlsChannelBindingType getType() {
        return cbType;
    }

    public byte[] getData() {
        return cbData;
    }
}
