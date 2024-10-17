/*
 * Copyright (c) 1997, 2022, Oracle and/or its affiliates. All rights reserved.
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

package sun.security.x509;

import java.security.PublicKey;
import java.io.InputStream;
import java.io.IOException;

import sun.security.util.*;

/**
 * This class defines the X509Key attribute for the Certificate.
 *
 * @author Amit Kapoor
 * @author Hemma Prafullchandra
 * @see DerEncoder
 */
public class CertificateX509Key implements DerEncoder {

    public static final String NAME = "key";

    // Private data member
    private PublicKey key;

    /**
     * Default constructor for the certificate attribute.
     *
     * @param key the X509Key
     */
    public CertificateX509Key(PublicKey key) {
        this.key = key;
    }

    /**
     * Create the object, decoding the values from the passed DER stream.
     *
     * @param in the DerInputStream to read the X509Key from.
     * @exception IOException on decoding errors.
     */
    public CertificateX509Key(DerInputStream in) throws IOException {
        DerValue val = in.getDerValue();
        key = X509Key.parse(val);
    }

    /**
     * Create the object, decoding the values from the passed stream.
     *
     * @param in the InputStream to read the X509Key from.
     * @exception IOException on decoding errors.
     */
    public CertificateX509Key(InputStream in) throws IOException {
        DerValue val = new DerValue(in);
        key = X509Key.parse(val);
    }

    /**
     * Return the key as printable string.
     */
    public String toString() {
        if (key == null) return "";
        return key.toString();
    }

    /**
     * Encode the key in DER form to the stream.
     *
     * @param out the DerOutputStream to marshal the contents to.
     */
    @Override
    public void encode(DerOutputStream out) {
        out.writeBytes(key.getEncoded());
    }

   /**
     * Get the PublicKey value.
     */
    public PublicKey getKey() {
        return key;
    }

}
