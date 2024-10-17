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

import java.util.List;

import jdk.internal.classfile.Annotation;
import jdk.internal.classfile.Attribute;
import jdk.internal.classfile.MethodElement;
import jdk.internal.classfile.MethodModel;
import jdk.internal.classfile.impl.BoundAttribute;
import jdk.internal.classfile.impl.UnboundAttribute;

/**
 * Models the {@code RuntimeInvisibleParameterAnnotations} attribute
 * {@jvms 4.7.19}, which can appear on methods. Delivered as a {@link
 * jdk.internal.classfile.MethodElement} when traversing a {@link MethodModel}.
 */
public sealed interface RuntimeInvisibleParameterAnnotationsAttribute
        extends Attribute<RuntimeInvisibleParameterAnnotationsAttribute>, MethodElement
        permits BoundAttribute.BoundRuntimeInvisibleParameterAnnotationsAttribute,
                UnboundAttribute.UnboundRuntimeInvisibleParameterAnnotationsAttribute {

    /**
     * {@return the list of annotations corresponding to each method parameter}
     * The element at the i'th index corresponds to the annotations on the i'th
     * parameter.
     */
    List<List<Annotation>> parameterAnnotations();

    /**
     * {@return a {@code RuntimeInvisibleParameterAnnotations} attribute}
     * @param parameterAnnotations a list of parameter annotations for each parameter
     */
    static RuntimeInvisibleParameterAnnotationsAttribute of(List<List<Annotation>> parameterAnnotations) {
        return new UnboundAttribute.UnboundRuntimeInvisibleParameterAnnotationsAttribute(parameterAnnotations);
    }
}
