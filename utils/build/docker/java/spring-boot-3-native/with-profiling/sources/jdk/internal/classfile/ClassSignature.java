/*
 * Copyright (c) 2022, Oracle and/or its affiliates. All rights reserved.
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
package jdk.internal.classfile;

import java.util.List;
import jdk.internal.classfile.impl.SignaturesImpl;
import static java.util.Objects.requireNonNull;

/**
 * Models the generic signature of a class file, as defined by {@jvms 4.7.9}.
 */
public sealed interface ClassSignature
        permits SignaturesImpl.ClassSignatureImpl {

    /** {@return the type parameters of this class} */
    List<Signature.TypeParam> typeParameters();

    /** {@return the instantiation of the superclass in this signature} */
    Signature.RefTypeSig superclassSignature();

    /** {@return the instantiation of the interfaces in this signature} */
    List<Signature.RefTypeSig> superinterfaceSignatures();

    /** {@return the raw signature string} */
    String signatureString();

    /**
     * @return class signature
     * @param superclassSignature the superclass
     * @param superinterfaceSignatures the interfaces
     */
    public static ClassSignature of(Signature.RefTypeSig superclassSignature,
                                    Signature.RefTypeSig... superinterfaceSignatures) {
        return of(List.of(), superclassSignature, superinterfaceSignatures);
    }

    /**
     * @return class signature
     * @param typeParameters the type parameters
     * @param superclassSignature the superclass
     * @param superinterfaceSignatures the interfaces
     */
    public static ClassSignature of(List<Signature.TypeParam> typeParameters,
                                    Signature.RefTypeSig superclassSignature,
                                    Signature.RefTypeSig... superinterfaceSignatures) {
        return new SignaturesImpl.ClassSignatureImpl(
                requireNonNull(typeParameters),
                requireNonNull(superclassSignature),
                List.of(superinterfaceSignatures));
    }

    /**
     * Parses a raw class signature string into a {@linkplain Signature}
     * @param classSignature the raw class signature string
     * @return class signature
     */
    public static ClassSignature parseFrom(String classSignature) {
        return new SignaturesImpl().parseClassSignature(requireNonNull(classSignature));
    }
}
