/*
 * Copyright (c) 2018, 2023, Oracle and/or its affiliates. All rights reserved.
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

package sun.security.ec;

import java.io.IOException;
import java.io.InvalidObjectException;
import java.io.ObjectInputStream;
import java.math.BigInteger;
import java.security.InvalidKeyException;
import java.security.KeyRep;
import java.security.interfaces.XECPublicKey;
import java.security.spec.AlgorithmParameterSpec;
import java.security.spec.NamedParameterSpec;
import java.util.Arrays;

import sun.security.util.BitArray;
import sun.security.x509.AlgorithmId;
import sun.security.x509.X509Key;

public final class XDHPublicKeyImpl extends X509Key implements XECPublicKey {

    @java.io.Serial
    private static final long serialVersionUID = 1L;

    private final BigInteger u;
    @SuppressWarnings("serial") // Type of field is not Serializable
    private final NamedParameterSpec paramSpec;

    XDHPublicKeyImpl(XECParameters params, BigInteger u)
        throws InvalidKeyException {

        this.paramSpec = new NamedParameterSpec(params.getName());
        this.algid = new AlgorithmId(params.getOid());
        this.u = u.mod(params.getP());

        byte[] u_arr = this.u.toByteArray();
        reverse(u_arr);
        // u_arr may be too large or too small, depending on the value of u
        u_arr = Arrays.copyOf(u_arr, params.getBytes());

        setKey(new BitArray(u_arr.length * 8, u_arr));

        checkLength(params);
    }

    XDHPublicKeyImpl(byte[] encoded) throws InvalidKeyException {
        decode(encoded);

        XECParameters params =
            XECParameters.get(InvalidKeyException::new, algid);
        this.paramSpec = new NamedParameterSpec(params.getName());
        // construct the BigInteger representation
        byte[] u_arr = getKey().toByteArray();
        reverse(u_arr);

        // clear the extra bits
        int bitsMod8 = params.getBits() % 8;
        if (bitsMod8 != 0) {
            byte mask = (byte) ((1 << bitsMod8) - 1);
            u_arr[0] &= mask;
        }

        this.u = new BigInteger(1, u_arr);

        checkLength(params);
    }

    void checkLength(XECParameters params) throws InvalidKeyException {

        if (params.getBytes() * 8 != getKey().length()) {
            throw new InvalidKeyException(
                "key length must be " + params.getBytes());
        }
    }

    @Override
    public BigInteger getU() {
        return u;
    }

    @Override
    public AlgorithmParameterSpec getParams() {
        return paramSpec;
    }

    @Override
    public String getAlgorithm() {
        return "XDH";
    }

    @java.io.Serial
    private Object writeReplace() throws java.io.ObjectStreamException {
        return new KeyRep(KeyRep.Type.PUBLIC,
            getAlgorithm(),
            getFormat(),
            getEncoded());
    }

    private static void swap(byte[] arr, int i, int j) {
        byte tmp = arr[i];
        arr[i] = arr[j];
        arr[j] = tmp;
    }

    private static void reverse(byte [] arr) {
        int i = 0;
        int j = arr.length - 1;

        while (i < j) {
            swap(arr, i, j);
            i++;
            j--;
        }
    }

    /**
     * Restores the state of this object from the stream.
     * <p>
     * Deserialization of this object is not supported.
     *
     * @param  stream the {@code ObjectInputStream} from which data is read
     * @throws IOException if an I/O error occurs
     * @throws ClassNotFoundException if a serialized class cannot be loaded
     */
    @java.io.Serial
    private void readObject(ObjectInputStream stream)
            throws IOException, ClassNotFoundException {
        throw new InvalidObjectException(
                "XDHPublicKeyImpl keys are not directly deserializable");
    }
}

