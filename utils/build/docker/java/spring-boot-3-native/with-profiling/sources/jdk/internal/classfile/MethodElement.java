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

import jdk.internal.classfile.attribute.AnnotationDefaultAttribute;
import jdk.internal.classfile.attribute.DeprecatedAttribute;
import jdk.internal.classfile.attribute.ExceptionsAttribute;
import jdk.internal.classfile.attribute.MethodParametersAttribute;
import jdk.internal.classfile.attribute.RuntimeInvisibleAnnotationsAttribute;
import jdk.internal.classfile.attribute.RuntimeInvisibleParameterAnnotationsAttribute;
import jdk.internal.classfile.attribute.RuntimeInvisibleTypeAnnotationsAttribute;
import jdk.internal.classfile.attribute.RuntimeVisibleAnnotationsAttribute;
import jdk.internal.classfile.attribute.RuntimeVisibleParameterAnnotationsAttribute;
import jdk.internal.classfile.attribute.RuntimeVisibleTypeAnnotationsAttribute;
import jdk.internal.classfile.attribute.SignatureAttribute;
import jdk.internal.classfile.attribute.SyntheticAttribute;
import jdk.internal.classfile.attribute.UnknownAttribute;

/**
 * A {@link ClassfileElement} that can appear when traversing the elements
 * of a {@link MethodModel} or be presented to a {@link MethodBuilder}.
 */
public sealed interface MethodElement
        extends ClassfileElement
        permits AccessFlags, CodeModel, CustomAttribute,
                AnnotationDefaultAttribute, DeprecatedAttribute,
                ExceptionsAttribute, MethodParametersAttribute,
                RuntimeInvisibleAnnotationsAttribute, RuntimeInvisibleParameterAnnotationsAttribute,
                RuntimeInvisibleTypeAnnotationsAttribute, RuntimeVisibleAnnotationsAttribute,
                RuntimeVisibleParameterAnnotationsAttribute, RuntimeVisibleTypeAnnotationsAttribute,
                SignatureAttribute, SyntheticAttribute, UnknownAttribute {

}
