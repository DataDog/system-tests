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

import jdk.internal.classfile.*;
import jdk.internal.classfile.impl.BoundAttribute;
import jdk.internal.classfile.impl.UnboundAttribute;

import java.util.List;

/**
 * Models the {@code RuntimeInvisibleAnnotations} attribute {@jvms 4.7.17}, which
 * can appear on classes, methods, and fields. Delivered as a
 * {@link jdk.internal.classfile.ClassElement}, {@link jdk.internal.classfile.FieldElement}, or
 * {@link jdk.internal.classfile.MethodElement} when traversing the corresponding model type.
 */
public sealed interface RuntimeInvisibleAnnotationsAttribute
        extends Attribute<RuntimeInvisibleAnnotationsAttribute>,
                ClassElement, MethodElement, FieldElement
        permits BoundAttribute.BoundRuntimeInvisibleAnnotationsAttribute,
                UnboundAttribute.UnboundRuntimeInvisibleAnnotationsAttribute {

    /**
     * {@return the non-runtime-visible annotations on this class, field, or method}
     */
    List<Annotation> annotations();

    /**
     * {@return a {@code RuntimeInvisibleAnnotations} attribute}
     * @param annotations the annotations
     */
    static RuntimeInvisibleAnnotationsAttribute of(List<Annotation> annotations) {
        return new UnboundAttribute.UnboundRuntimeInvisibleAnnotationsAttribute(annotations);
    }

    /**
     * {@return a {@code RuntimeInvisibleAnnotations} attribute}
     * @param annotations the annotations
     */
    static RuntimeInvisibleAnnotationsAttribute of(Annotation... annotations) {
        return of(List.of(annotations));
    }
}
