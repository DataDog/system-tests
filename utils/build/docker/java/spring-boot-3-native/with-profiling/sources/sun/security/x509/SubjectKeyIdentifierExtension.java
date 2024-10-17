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

import sun.security.util.*;

/**
 * Represent the Subject Key Identifier Extension.
 *
 * This extension, if present, provides a means of identifying the particular
 * public key used in an application.  This extension by default is marked
 * non-critical.
 *
 * <p>Extensions are additional attributes which can be inserted in a X509
 * v3 certificate. For example a "Driving License Certificate" could have
 * the driving license number as an extension.
 *
 * <p>Extensions are represented as a sequence of the extension identifier
 * (Object Identifier), a boolean flag stating whether the extension is to
 * be treated as being critical and the extension value itself (this is again
 * a DER encoding of the extension value).
 *
 * @author Amit Kapoor
 * @author Hemma Prafullchandra
 * @see Extension
 */
public class SubjectKeyIdentifierExtension extends Extension {

    public static final String NAME = "SubjectKeyIdentifier";

    // Private data member
    private KeyIdentifier id;

    // Encode this extension value
    private void encodeThis() {
        if (id == null) {
            this.extensionValue = null;
            return;
        }
        DerOutputStream os = new DerOutputStream();
        id.encode(os);
        this.extensionValue = os.toByteArray();
    }

    /**
     * Create a SubjectKeyIdentifierExtension with the passed octet string.
     * The criticality is set to False.
     * @param octetString the octet string identifying the key identifier.
     */
    public SubjectKeyIdentifierExtension(byte[] octetString) {
        id = new KeyIdentifier(octetString);

        this.extensionId = PKIXExtensions.SubjectKey_Id;
        this.critical = false;
        encodeThis();
    }

    /**
     * Create the extension from the passed DER encoded value.
     *
     * @param critical true if the extension is to be treated as critical.
     * @param value an array of DER encoded bytes of the actual value.
     * @exception ClassCastException if value is not an array of bytes
     * @exception IOException on error.
     */
    public SubjectKeyIdentifierExtension(Boolean critical, Object value)
    throws IOException {
        this.extensionId = PKIXExtensions.SubjectKey_Id;
        this.critical = critical.booleanValue();
        this.extensionValue = (byte[]) value;
        DerValue val = new DerValue(this.extensionValue);
        this.id = new KeyIdentifier(val);
    }

    /**
     * Returns a printable representation.
     */
    public String toString() {
        return super.toString() +
            "SubjectKeyIdentifier [\n" + id + "]\n";
    }

    /**
     * Write the extension to the OutputStream.
     *
     * @param out the DerOutputStream to write the extension to.
     */
    @Override
    public void encode(DerOutputStream out) {
        if (extensionValue == null) {
            extensionId = PKIXExtensions.SubjectKey_Id;
            critical = false;
            encodeThis();
        }
        super.encode(out);
    }

    public KeyIdentifier getKeyIdentifier() {
        return id;
    }

    /**
     * Return the name of this extension.
     */
    @Override
    public String getName() {
        return NAME;
    }
}
