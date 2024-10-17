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

import java.lang.constant.MethodTypeDesc;
import java.util.Optional;

import jdk.internal.classfile.constantpool.Utf8Entry;
import jdk.internal.classfile.impl.BufferedMethodBuilder;
import jdk.internal.classfile.impl.MethodImpl;

/**
 * Models a method.  The contents of the method can be traversed via
 * a streaming view (e.g., {@link #elements()}), or via random access (e.g.,
 * {@link #flags()}), or by freely mixing the two.
 */
public sealed interface MethodModel
        extends WritableElement<MethodModel>, CompoundElement<MethodElement>, AttributedElement, ClassElement
        permits BufferedMethodBuilder.Model, MethodImpl {

    /** {@return the access flags} */
    AccessFlags flags();

    /** {@return the class model this method is a member of, if known} */
    Optional<ClassModel> parent();

    /** {@return the name of this method} */
    Utf8Entry methodName();

    /** {@return the method descriptor of this method} */
    Utf8Entry methodType();

    /** {@return the method descriptor of this method, as a symbolic descriptor} */
    default MethodTypeDesc methodTypeSymbol() {
        return MethodTypeDesc.ofDescriptor(methodType().stringValue());
    }

    /** {@return the body of this method, if there is one} */
    Optional<CodeModel> code();
}
