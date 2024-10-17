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

import sun.security.util.BitArray;
import sun.security.util.DerInputStream;
import sun.security.util.DerOutputStream;
import sun.security.util.DerValue;

/**
 * This class defines the UniqueIdentity class used by certificates.
 *
 * @author Amit Kapoor
 * @author Hemma Prafullchandra
 */
public class UniqueIdentity {
    // Private data members
    private final BitArray    id;

    /**
     * The default constructor for this class.
     *
     * @param id the byte array containing the unique identifier.
     */
    public UniqueIdentity(BitArray id) {
        this.id = id;
    }

    /**
     * The default constructor for this class.
     *
     * @param id the byte array containing the unique identifier.
     */
    public UniqueIdentity(byte[] id) {
        this.id = new BitArray(id.length*8, id);
    }

    /**
     * Create the object, decoding the values from the passed DER stream.
     *
     * @param in the DerInputStream to read the UniqueIdentity from.
     * @exception IOException on decoding errors.
     */
    public UniqueIdentity(DerInputStream in) throws IOException {
        DerValue derVal = in.getDerValue();
        id = derVal.getUnalignedBitString(true);
    }

    /**
     * Create the object, decoding the values from the passed DER stream.
     *
     * @param derVal the DerValue decoded from the stream.
     * @exception IOException on decoding errors.
     */
    public UniqueIdentity(DerValue derVal) throws IOException {
        id = derVal.getUnalignedBitString(true);
    }

    /**
     * Return the UniqueIdentity as a printable string.
     */
    public String toString() {
        return ("UniqueIdentity:" + id.toString() + "\n");
    }

    /**
     * Encode the UniqueIdentity in DER form to the stream.
     *
     * @param out the DerOutputStream to marshal the contents to.
     * @param tag encode it under the following tag.
     */
    public void encode(DerOutputStream out, byte tag) {
        byte[] bytes = id.toByteArray();
        int excessBits = bytes.length*8 - id.length();

        out.write(tag);
        out.putLength(bytes.length + 1);

        out.write(excessBits);
        out.writeBytes(bytes);
    }

    /**
     * Return the unique id.
     */
    public boolean[] getId() {
        if (id == null) return null;

        return id.toBooleanArray();
    }
}
