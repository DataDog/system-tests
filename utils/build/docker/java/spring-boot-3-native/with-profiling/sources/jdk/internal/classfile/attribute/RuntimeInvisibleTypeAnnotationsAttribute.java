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
 * Models the {@code RuntimeInvisibleTypeAnnotations} attribute {@jvms 4.7.21}, which
 * can appear on classes, methods, fields, and code attributes. Delivered as a
 * {@link jdk.internal.classfile.ClassElement}, {@link jdk.internal.classfile.FieldElement},
 * {@link jdk.internal.classfile.MethodElement}, or {@link CodeElement} when traversing
 * the corresponding model type.
 */
public sealed interface RuntimeInvisibleTypeAnnotationsAttribute
        extends Attribute<RuntimeInvisibleTypeAnnotationsAttribute>,
                ClassElement, MethodElement, FieldElement, CodeElement
        permits BoundAttribute.BoundRuntimeInvisibleTypeAnnotationsAttribute,
                UnboundAttribute.UnboundRuntimeInvisibleTypeAnnotationsAttribute {

    /**
     * {@return the non-runtime-visible type annotations on parts of this class, field, or method}
     */
    List<TypeAnnotation> annotations();

    /**
     * {@return a {@code RuntimeInvisibleTypeAnnotations} attribute}
     * @param annotations the annotations
     */
    static RuntimeInvisibleTypeAnnotationsAttribute of(List<TypeAnnotation> annotations) {
        return new UnboundAttribute.UnboundRuntimeInvisibleTypeAnnotationsAttribute(annotations);
    }

    /**
     * {@return a {@code RuntimeInvisibleTypeAnnotations} attribute}
     * @param annotations the annotations
     */
    static RuntimeInvisibleTypeAnnotationsAttribute of(TypeAnnotation... annotations) {
        return of(List.of(annotations));
    }
}
