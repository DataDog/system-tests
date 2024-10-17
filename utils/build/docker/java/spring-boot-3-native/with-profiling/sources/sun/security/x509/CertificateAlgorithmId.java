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

import java.io.IOException;
import java.io.InputStream;

import sun.security.util.*;

/**
 * This class defines the AlgorithmId for the Certificate.
 *
 * @author Amit Kapoor
 * @author Hemma Prafullchandra
 */
public class CertificateAlgorithmId implements DerEncoder {
    private AlgorithmId algId;

    public static final String NAME = "algorithmID";

    /**
     * Default constructor for the certificate attribute.
     *
     * @param algId the Algorithm identifier
     */
    public CertificateAlgorithmId(AlgorithmId algId) {
        this.algId = algId;
    }

    /**
     * Create the object, decoding the values from the passed DER stream.
     *
     * @param in the DerInputStream to read the serial number from.
     * @exception IOException on decoding errors.
     */
    public CertificateAlgorithmId(DerInputStream in) throws IOException {
        DerValue val = in.getDerValue();
        algId = AlgorithmId.parse(val);
    }

    /**
     * Create the object, decoding the values from the passed stream.
     *
     * @param in the InputStream to read the serial number from.
     * @exception IOException on decoding errors.
     */
    public CertificateAlgorithmId(InputStream in) throws IOException {
        DerValue val = new DerValue(in);
        algId = AlgorithmId.parse(val);
    }

    /**
     * Return the algorithm identifier as user readable string.
     */
    public String toString() {
        if (algId == null) return "";
        return (algId.toString() +
                ", OID = " + (algId.getOID()).toString() + "\n");
    }

    /**
     * Encode the algorithm identifier in DER form to the stream.
     *
     * @param out the DerOutputStream to marshal the contents to.
     */
    @Override
    public void encode(DerOutputStream out) {
        algId.encode(out);
    }

    /**
     * Get the AlgorithmId value.
     */
    public AlgorithmId getAlgId() throws IOException {
        return algId;
    }
}
