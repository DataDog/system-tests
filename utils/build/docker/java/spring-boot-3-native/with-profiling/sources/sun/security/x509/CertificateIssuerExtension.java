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
package sun.security.x509;

import java.io.IOException;

import sun.security.util.DerValue;
import sun.security.util.DerOutputStream;

/**
 * Represents the CRL Certificate Issuer Extension (OID = 2.5.29.29).
 * <p>
 * The CRL certificate issuer extension identifies the certificate issuer
 * associated with an entry in an indirect CRL, i.e. a CRL that has the
 * indirectCRL indicator set in its issuing distribution point extension. If
 * this extension is not present on the first entry in an indirect CRL, the
 * certificate issuer defaults to the CRL issuer. On subsequent entries
 * in an indirect CRL, if this extension is not present, the certificate
 * issuer for the entry is the same as that for the preceding entry.
 * <p>
 * If used by conforming CRL issuers, this extension is always
 * critical.  If an implementation ignored this extension it could not
 * correctly attribute CRL entries to certificates.  PKIX (RFC 5280)
 * RECOMMENDS that implementations recognize this extension.
 * <p>
 * The ASN.1 definition for this is:
 * <pre>
 * id-ce-certificateIssuer   OBJECT IDENTIFIER ::= { id-ce 29 }
 *
 * certificateIssuer ::=     GeneralNames
 * </pre>
 *
 * @author Anne Anderson
 * @author Sean Mullan
 * @since 1.5
 * @see Extension
 */
public class CertificateIssuerExtension extends Extension {

    public static final String NAME = "CertificateIssuer";

    private GeneralNames names;

    /**
     * Encode this extension
     */
    private void encodeThis() {
        if (names == null || names.isEmpty()) {
            this.extensionValue = null;
            return;
        }
        DerOutputStream os = new DerOutputStream();
        names.encode(os);
        this.extensionValue = os.toByteArray();
    }

    /**
     * Create a CertificateIssuerExtension containing the specified issuer name.
     * Criticality is automatically set to true.
     *
     * @param issuer the certificate issuer, cannot be null or empty.
     */
    public CertificateIssuerExtension(GeneralNames issuer) {
        if (issuer == null || issuer.isEmpty()) {
            throw new IllegalArgumentException("issuer cannot be null or empty");
        }
        this.extensionId = PKIXExtensions.CertificateIssuer_Id;
        this.critical = true;
        this.names = issuer;
        encodeThis();
    }

    /**
     * Create a CertificateIssuerExtension from the specified DER encoded
     * value of the same.
     *
     * @param critical true if the extension is to be treated as critical.
     * @param value an array of DER encoded bytes of the actual value
     * @throws ClassCastException if value is not an array of bytes
     * @throws IOException on error
     */
    public CertificateIssuerExtension(Boolean critical, Object value)
        throws IOException {
        this.extensionId = PKIXExtensions.CertificateIssuer_Id;
        this.critical = critical.booleanValue();

        this.extensionValue = (byte[]) value;
        DerValue val = new DerValue(this.extensionValue);
        this.names = new GeneralNames(val);
    }

    public GeneralNames getNames() {
        return names;
    }

    /**
     * Returns a printable representation of the certificate issuer.
     */
    public String toString() {
        return super.toString() + "Certificate Issuer [\n" +
            names + "]\n";
    }

    /**
     * Write the extension to the OutputStream.
     *
     * @param out the DerOutputStream to write the extension to
     */
    @Override
    public void encode(DerOutputStream out) {
        if (extensionValue == null) {
            extensionId = PKIXExtensions.CertificateIssuer_Id;
            critical = true;
            encodeThis();
        }
        super.encode(out);
    }


    /**
     * Return the name of this extension.
     */
    @Override
    public String getName() {
        return NAME;
    }
}
