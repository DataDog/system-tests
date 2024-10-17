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

package jdk.internal.classfile.attribute;

import jdk.internal.classfile.AnnotationValue;
import jdk.internal.classfile.Attribute;
import jdk.internal.classfile.MethodElement;
import jdk.internal.classfile.MethodModel;
import jdk.internal.classfile.impl.BoundAttribute;
import jdk.internal.classfile.impl.UnboundAttribute;

/**
 * Models the {@code AnnotationDefault} attribute {@jvms 4.7.22}, which can
 * appear on methods of annotation types, and records the default value
 * {@jls 9.6.2} for the element corresponding to this method.  Delivered as a
 * {@link MethodElement} when traversing the elements of a {@link MethodModel}.
 */
public sealed interface AnnotationDefaultAttribute
        extends Attribute<AnnotationDefaultAttribute>, MethodElement
        permits BoundAttribute.BoundAnnotationDefaultAttr,
                UnboundAttribute.UnboundAnnotationDefaultAttribute {

    /**
     * {@return the default value of the annotation type element represented by
     * this method}
     */
    AnnotationValue defaultValue();

    /**
     * {@return an {@code AnnotationDefault} attribute}
     * @param annotationDefault the default value of the annotation type element
     */
    static AnnotationDefaultAttribute of(AnnotationValue annotationDefault) {
        return new UnboundAttribute.UnboundAnnotationDefaultAttribute(annotationDefault);
    }

}
