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

import java.lang.constant.ClassDesc;
import java.util.Optional;

import jdk.internal.classfile.constantpool.Utf8Entry;
import jdk.internal.classfile.impl.BufferedFieldBuilder;
import jdk.internal.classfile.impl.FieldImpl;

/**
 * Models a field.  The contents of the field can be traversed via
 * a streaming view (e.g., {@link #elements()}), or via random access (e.g.,
 * {@link #flags()}), or by freely mixing the two.
 */
public sealed interface FieldModel
        extends WritableElement<FieldModel>, CompoundElement<FieldElement>, AttributedElement, ClassElement
        permits BufferedFieldBuilder.Model, FieldImpl {

    /** {@return the access flags} */
    AccessFlags flags();

    /** {@return the class model this field is a member of, if known} */
    Optional<ClassModel> parent();

    /** {@return the name of this field} */
    Utf8Entry fieldName();

    /** {@return the field descriptor of this field} */
    Utf8Entry fieldType();

    /** {@return the field descriptor of this field, as a symbolic descriptor} */
    default ClassDesc fieldTypeSymbol() {
        return ClassDesc.ofDescriptor(fieldType().stringValue());
    }
}
