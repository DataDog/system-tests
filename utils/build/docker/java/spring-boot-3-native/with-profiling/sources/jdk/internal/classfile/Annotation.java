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

import jdk.internal.classfile.attribute.RuntimeInvisibleAnnotationsAttribute;
import jdk.internal.classfile.attribute.RuntimeInvisibleParameterAnnotationsAttribute;
import jdk.internal.classfile.attribute.RuntimeVisibleAnnotationsAttribute;
import jdk.internal.classfile.attribute.RuntimeVisibleParameterAnnotationsAttribute;
import jdk.internal.classfile.constantpool.Utf8Entry;
import jdk.internal.classfile.impl.AnnotationImpl;
import jdk.internal.classfile.impl.TemporaryConstantPool;

import java.lang.constant.ClassDesc;
import java.util.List;

/**
 * Models an annotation on a declaration.
 *
 * @see AnnotationElement
 * @see AnnotationValue
 * @see RuntimeVisibleAnnotationsAttribute
 * @see RuntimeInvisibleAnnotationsAttribute
 * @see RuntimeVisibleParameterAnnotationsAttribute
 * @see RuntimeInvisibleParameterAnnotationsAttribute
 */
public sealed interface Annotation
        extends WritableElement<Annotation>
        permits TypeAnnotation, AnnotationImpl {

    /**
     * {@return the class of the annotation}
     */
    Utf8Entry className();

    /**
     * {@return the class of the annotation, as a symbolic descriptor}
     */
    default ClassDesc classSymbol() {
        return ClassDesc.ofDescriptor(className().stringValue());
    }

    /**
     * {@return the elements of the annotation}
     */
    List<AnnotationElement> elements();

    /**
     * {@return an annotation}
     * @param annotationClass the class of the annotation
     * @param elements the elements of the annotation
     */
    static Annotation of(Utf8Entry annotationClass,
                         List<AnnotationElement> elements) {
        return new AnnotationImpl(annotationClass, elements);
    }

    /**
     * {@return an annotation}
     * @param annotationClass the class of the annotation
     * @param elements the elements of the annotation
     */
    static Annotation of(Utf8Entry annotationClass,
                         AnnotationElement... elements) {
        return of(annotationClass, List.of(elements));
    }

    /**
     * {@return an annotation}
     * @param annotationClass the class of the annotation
     * @param elements the elements of the annotation
     */
    static Annotation of(ClassDesc annotationClass,
                         List<AnnotationElement> elements) {
        return of(TemporaryConstantPool.INSTANCE.utf8Entry(annotationClass.descriptorString()), elements);
    }

    /**
     * {@return an annotation}
     * @param annotationClass the class of the annotation
     * @param elements the elements of the annotation
     */
    static Annotation of(ClassDesc annotationClass,
                         AnnotationElement... elements) {
        return of(TemporaryConstantPool.INSTANCE.utf8Entry(annotationClass.descriptorString()), elements);
    }
}
