/*
 * Copyright (c) 2020, 2023, Oracle and/or its affiliates. All rights reserved.
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

package sun.security.ec.ed;

import java.io.IOException;
import java.io.InvalidObjectException;
import java.io.ObjectInputStream;
import java.math.BigInteger;
import java.security.InvalidKeyException;
import java.security.KeyRep;
import java.security.interfaces.EdECPublicKey;
import java.security.spec.EdECPoint;
import java.security.spec.NamedParameterSpec;
import java.util.Arrays;

import sun.security.util.BitArray;
import sun.security.x509.AlgorithmId;
import sun.security.x509.X509Key;

public final class EdDSAPublicKeyImpl extends X509Key implements EdECPublicKey {

    @java.io.Serial
    private static final long serialVersionUID = 1L;

    @SuppressWarnings("serial") // Type of field is not Serializable
    private final EdECPoint point;
    @SuppressWarnings("serial") // Type of field is not Serializable
    private final NamedParameterSpec paramSpec;

    public EdDSAPublicKeyImpl(EdDSAParameters params, EdECPoint point)
            throws InvalidKeyException {
        this.paramSpec = new NamedParameterSpec(params.getName());
        this.algid = new AlgorithmId(params.getOid());
        this.point = point;

        byte[] encodedPoint = point.getY().toByteArray();
        reverse(encodedPoint);
        // array may be too large or too small, depending on the value
        encodedPoint = Arrays.copyOf(encodedPoint, params.getKeyLength());
        // set the high-order bit of the encoded point
        byte msb = (byte) (point.isXOdd() ? 0x80 : 0);
        encodedPoint[encodedPoint.length - 1] |= msb;
        setKey(new BitArray(encodedPoint.length * 8, encodedPoint));

        checkLength(params);
    }

    public EdDSAPublicKeyImpl(byte[] encoded) throws InvalidKeyException {
        decode(encoded);

        EdDSAParameters params =
            EdDSAParameters.get(InvalidKeyException::new, algid);
        this.paramSpec = new NamedParameterSpec(params.getName());
        // construct the EdECPoint representation
        byte[] encodedPoint = getKey().toByteArray();
        byte msb = encodedPoint[encodedPoint.length - 1];
        encodedPoint[encodedPoint.length - 1] &= (byte) 0x7F;
        boolean xOdd = (msb & 0x80) != 0;
        reverse(encodedPoint);
        BigInteger y = new BigInteger(1, encodedPoint);
        this.point = new EdECPoint(xOdd, y);

        checkLength(params);
    }

    void checkLength(EdDSAParameters params) throws InvalidKeyException {
        if (params.getKeyLength() * 8 != getKey().length()) {
            throw new InvalidKeyException(
                "key length must be " + params.getKeyLength());
        }
    }

    public byte[] getEncodedPoint() {
        return getKey().toByteArray();
    }

    @Override
    public EdECPoint getPoint() {
        return point;
    }

    @Override
    public NamedParameterSpec getParams() {
        return paramSpec;
    }

    @Override
    public String getAlgorithm() {
        return "EdDSA";
    }

    @java.io.Serial
    private Object writeReplace() throws java.io.ObjectStreamException {
        return new KeyRep(KeyRep.Type.PUBLIC, getAlgorithm(), getFormat(),
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
                "EdDSAPublicKeyImpl keys are not directly deserializable");
    }
}
