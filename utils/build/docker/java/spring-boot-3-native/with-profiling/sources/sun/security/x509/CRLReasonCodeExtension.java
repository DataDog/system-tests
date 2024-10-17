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
import java.security.cert.CRLReason;

import sun.security.util.*;

/**
 * The reasonCode is a non-critical CRL entry extension that identifies
 * the reason for the certificate revocation.
 * @author Hemma Prafullchandra
 * @see java.security.cert.CRLReason
 * @see Extension
 */
public class CRLReasonCodeExtension extends Extension {

    public static final String NAME = "CRLReasonCode";

    private static final CRLReason[] values = CRLReason.values();

    private int reasonCode;

    private void encodeThis() {
        if (reasonCode == 0) {
            this.extensionValue = null;
            return;
        }
        DerOutputStream dos = new DerOutputStream();
        dos.putEnumerated(reasonCode);
        this.extensionValue = dos.toByteArray();
    }

    /**
     * Create a CRLReasonCodeExtension with the passed in reason.
     * Criticality automatically set to false.
     *
     * @param reason the enumerated value for the reason code.
     */
    public CRLReasonCodeExtension(int reason) throws IOException {
        this(false, reason);
    }

    /**
     * Create a CRLReasonCodeExtension with the passed in reason.
     *
     * @param critical true if the extension is to be treated as critical.
     * @param reason the enumerated value for the reason code, must be positive.
     */
    public CRLReasonCodeExtension(boolean critical, int reason) {
        if (reason <= 0) {
            throw new IllegalArgumentException("reason code must be positive");
        }
        this.extensionId = PKIXExtensions.ReasonCode_Id;
        this.critical = critical;
        this.reasonCode = reason;
        encodeThis();
    }

    /**
     * Create the extension from the passed DER encoded value of the same.
     *
     * @param critical true if the extension is to be treated as critical.
     * @param value an array of DER encoded bytes of the actual value.
     * @exception ClassCastException if value is not an array of bytes
     * @exception IOException on error.
     */
    public CRLReasonCodeExtension(Boolean critical, Object value)
    throws IOException {
        this.extensionId = PKIXExtensions.ReasonCode_Id;
        this.critical = critical.booleanValue();
        this.extensionValue = (byte[]) value;
        DerValue val = new DerValue(this.extensionValue);
        this.reasonCode = val.getEnumerated();
    }

    /**
     * Returns a printable representation of the Reason code.
     */
    public String toString() {
        return super.toString() + "    Reason Code: " + getReasonCode();
    }

    /**
     * Write the extension to the DerOutputStream.
     *
     * @param out the DerOutputStream to write the extension to.
     */
    @Override
    public void encode(DerOutputStream out) {
        if (this.extensionValue == null) {
            this.extensionId = PKIXExtensions.ReasonCode_Id;
            this.critical = false;
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

    /**
     * Return the reason as a CRLReason enum.
     */
    public CRLReason getReasonCode() {
        // if out-of-range, return UNSPECIFIED
        if (reasonCode > 0 && reasonCode < values.length) {
            return values[reasonCode];
        } else {
            return CRLReason.UNSPECIFIED;
        }
    }

    public int getReason() {
        return reasonCode;
    }
}
