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
 * This class represents the Basic Constraints Extension.
 *
 * <p>The basic constraints extension identifies whether the subject of the
 * certificate is a CA and how deep a certification path may exist
 * through that CA.
 *
 * <pre>
 * The ASN.1 syntax for this extension is:
 * BasicConstraints ::= SEQUENCE {
 *     cA                BOOLEAN DEFAULT FALSE,
 *     pathLenConstraint INTEGER (0..MAX) OPTIONAL
 * }
 * </pre>
 * @author Amit Kapoor
 * @author Hemma Prafullchandra
 * @see Extension
 */
public class BasicConstraintsExtension extends Extension {

    public static final String NAME = "BasicConstraints";

    // Private data members
    private boolean     ca = false;
    private int pathLen = -1;

    // Encode this extension value
    private void encodeThis() {
        DerOutputStream out = new DerOutputStream();
        DerOutputStream tmp = new DerOutputStream();

        if (ca) {
            tmp.putBoolean(true);
            // Only encode pathLen when ca == true
            if (pathLen >= 0) {
                tmp.putInteger(pathLen);
            }
        }
        out.write(DerValue.tag_Sequence, tmp);
        this.extensionValue = out.toByteArray();
    }

    /**
     * Default constructor for this object. The extension is marked
     * critical if the ca flag is true, false otherwise.
     *
     * @param ca true, if the subject of the Certificate is a CA.
     * @param len specifies the depth of the certification path.
     */
    public BasicConstraintsExtension(boolean ca, int len) {
        this(Boolean.valueOf(ca), ca, len);
    }

    /**
     * Constructor for this object with specified criticality.
     *
     * @param critical true, if the extension should be marked critical
     * @param ca true, if the subject of the Certificate is a CA.
     * @param len specifies the depth of the certification path.
     */
    public BasicConstraintsExtension(Boolean critical, boolean ca, int len) {
        this.ca = ca;
        this.pathLen = len;
        this.extensionId = PKIXExtensions.BasicConstraints_Id;
        this.critical = critical.booleanValue();
        encodeThis();
    }

    /**
     * Create the extension from the passed DER encoded value of the same.
     *
     * @param critical flag indicating if extension is critical or not
     * @param value an array containing the DER encoded bytes of the extension.
     * @exception ClassCastException if value is not an array of bytes
     * @exception IOException on error.
     */
     public BasicConstraintsExtension(Boolean critical, Object value)
         throws IOException
    {
         this.extensionId = PKIXExtensions.BasicConstraints_Id;
         this.critical = critical.booleanValue();

         this.extensionValue = (byte[]) value;
         DerValue val = new DerValue(this.extensionValue);
         if (val.tag != DerValue.tag_Sequence) {
             throw new IOException("Invalid encoding of BasicConstraints");
         }

         if (val.data == null || val.data.available() == 0) {
             // non-CA cert ("cA" field is FALSE by default), return -1
             return;
         }
         DerValue opt = val.data.getDerValue();
         if (opt.tag != DerValue.tag_Boolean) {
             // non-CA cert ("cA" field is FALSE by default), return -1
             return;
         }

         this.ca = opt.getBoolean();
         if (val.data.available() == 0) {
             // From PKIX profile:
             // Where pathLenConstraint does not appear, there is no
             // limit to the allowed length of the certification path.
             this.pathLen = Integer.MAX_VALUE;
             return;
         }

         opt = val.data.getDerValue();
         if (opt.tag != DerValue.tag_Integer) {
             throw new IOException("Invalid encoding of BasicConstraints");
         }
         this.pathLen = opt.getInteger();
         /*
          * Activate this check once again after PKIX profiling
          * is a standard and this check no longer imposes an
          * interoperability barrier.
          * if (ca) {
          *   if (!this.critical) {
          *   throw new IOException("Criticality cannot be false for CA.");
          *   }
          * }
          */
     }

     /**
      * Return user readable form of extension.
      */
     public String toString() {
         String pathLenAsString;
         if (pathLen < 0) {
             pathLenAsString = " undefined";
         } else if (pathLen == Integer.MAX_VALUE) {
             pathLenAsString = " no limit";
         } else {
             pathLenAsString = String.valueOf(pathLen);
         }
         return super.toString() +
             "BasicConstraints:[\n  CA:" + ca +
             "\n  PathLen:" + pathLenAsString +
             "\n]\n";
     }

     /**
      * Encode this extension value to the output stream.
      *
      * @param out the DerOutputStream to encode the extension to.
      */
     @Override
     public void encode(DerOutputStream out) {
         if (extensionValue == null) {
             this.extensionId = PKIXExtensions.BasicConstraints_Id;
             critical = ca;
             encodeThis();
         }
         super.encode(out);
     }

    public boolean isCa() {
        return ca;
    }

    public int getPathLen() {
        return pathLen;
    }

    /**
     * Return the name of this extension.
     */
    @Override
    public String getName() {
        return NAME;
    }
}
