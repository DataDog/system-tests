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

import jdk.internal.classfile.Attribute;
import jdk.internal.classfile.ClassElement;
import jdk.internal.classfile.CodeElement;
import jdk.internal.classfile.FieldElement;
import jdk.internal.classfile.MethodElement;
import jdk.internal.classfile.TypeAnnotation;
import jdk.internal.classfile.impl.BoundAttribute;
import jdk.internal.classfile.impl.UnboundAttribute;

/**
 * Models the {@code RuntimeVisibleTypeAnnotations} attribute {@jvms 4.7.20}, which
 * can appear on classes, methods, fields, and code attributes. Delivered as a
 * {@link jdk.internal.classfile.ClassElement}, {@link jdk.internal.classfile.FieldElement},
 * {@link jdk.internal.classfile.MethodElement}, or {@link CodeElement} when traversing
 * the corresponding model type.
 */
public sealed interface RuntimeVisibleTypeAnnotationsAttribute
        extends Attribute<RuntimeVisibleTypeAnnotationsAttribute>,
                ClassElement, MethodElement, FieldElement, CodeElement
        permits BoundAttribute.BoundRuntimeVisibleTypeAnnotationsAttribute,
                UnboundAttribute.UnboundRuntimeVisibleTypeAnnotationsAttribute {

    /**
     * {@return the runtime-visible type annotations on parts of this class, field, or method}
     */
    List<TypeAnnotation> annotations();

    /**
     * {@return a {@code RuntimeVisibleTypeAnnotations} attribute}
     * @param annotations the annotations
     */
    static RuntimeVisibleTypeAnnotationsAttribute of(List<TypeAnnotation> annotations) {
        return new UnboundAttribute.UnboundRuntimeVisibleTypeAnnotationsAttribute(annotations);
    }

    /**
     * {@return a {@code RuntimeVisibleTypeAnnotations} attribute}
     * @param annotations the annotations
     */
    static RuntimeVisibleTypeAnnotationsAttribute of(TypeAnnotation... annotations) {
        return of(List.of(annotations));
    }
}
