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

import jdk.internal.classfile.constantpool.Utf8Entry;
import jdk.internal.classfile.impl.AnnotationImpl;
import jdk.internal.classfile.impl.TemporaryConstantPool;

/**
 * Models a key-value pair of an annotation.
 *
 * @see Annotation
 * @see AnnotationValue
 */
public sealed interface AnnotationElement
        extends WritableElement<AnnotationElement>
        permits AnnotationImpl.AnnotationElementImpl {

    /**
     * {@return the element name}
     */
    Utf8Entry name();

    /**
     * {@return the element value}
     */
    AnnotationValue value();

    /**
     * {@return an annotation key-value pair}
     * @param name the name of the key
     * @param value the associated value
     */
    static AnnotationElement of(Utf8Entry name,
                                AnnotationValue value) {
        return new AnnotationImpl.AnnotationElementImpl(name, value);
    }

    /**
     * {@return an annotation key-value pair}
     * @param name the name of the key
     * @param value the associated value
     */
    static AnnotationElement of(String name,
                                AnnotationValue value) {
        return of(TemporaryConstantPool.INSTANCE.utf8Entry(name), value);
    }

    /**
     * {@return an annotation key-value pair for a class-valued annotation}
     * @param name the name of the key
     * @param value the associated value
     */
    static AnnotationElement ofClass(String name,
                                     ClassDesc value) {
        return of(name, AnnotationValue.ofClass(value));
    }

    /**
     * {@return an annotation key-value pair for a string-valued annotation}
     * @param name the name of the key
     * @param value the associated value
     */
    static AnnotationElement ofString(String name,
                                      String value) {
        return of(name, AnnotationValue.ofString(value));
    }

    /**
     * {@return an annotation key-value pair for a long-valued annotation}
     * @param name the name of the key
     * @param value the associated value
     */
    static AnnotationElement ofLong(String name,
                                    long value) {
        return of(name, AnnotationValue.ofLong(value));
    }

    /**
     * {@return an annotation key-value pair for an int-valued annotation}
     * @param name the name of the key
     * @param value the associated value
     */
    static AnnotationElement ofInt(String name,
                                   int value) {
        return of(name, AnnotationValue.ofInt(value));
    }

    /**
     * {@return an annotation key-value pair for a char-valued annotation}
     * @param name the name of the key
     * @param value the associated value
     */
    static AnnotationElement ofChar(String name,
                                    char value) {
        return of(name, AnnotationValue.ofChar(value));
    }

    /**
     * {@return an annotation key-value pair for a short-valued annotation}
     * @param name the name of the key
     * @param value the associated value
     */
    static AnnotationElement ofShort(String name,
                                     short value) {
        return of(name, AnnotationValue.ofShort(value));
    }

    /**
     * {@return an annotation key-value pair for a byte-valued annotation}
     * @param name the name of the key
     * @param value the associated value
     */
    static AnnotationElement ofByte(String name,
                                      byte value) {
        return of(name, AnnotationValue.ofByte(value));
    }

    /**
     * {@return an annotation key-value pair for a boolean-valued annotation}
     * @param name the name of the key
     * @param value the associated value
     */
    static AnnotationElement ofBoolean(String name,
                                      boolean value) {
        return of(name, AnnotationValue.ofBoolean(value));
    }

    /**
     * {@return an annotation key-value pair for a double-valued annotation}
     * @param name the name of the key
     * @param value the associated value
     */
    static AnnotationElement ofDouble(String name,
                                      double value) {
        return of(name, AnnotationValue.ofDouble(value));
    }

    /**
     * {@return an annotation key-value pair for a float-valued annotation}
     * @param name the name of the key
     * @param value the associated value
     */
    static AnnotationElement ofFloat(String name,
                                     float value) {
        return of(name, AnnotationValue.ofFloat(value));
    }

    /**
     * {@return an annotation key-value pair for an annotation-valued annotation}
     * @param name the name of the key
     * @param value the associated value
     */
    static AnnotationElement ofAnnotation(String name,
                                          Annotation value) {
        return of(name, AnnotationValue.ofAnnotation(value));
    }

    /**
     * {@return an annotation key-value pair for an array-valued annotation}
     * @param name the name of the key
     * @param values the associated values
     */
    static AnnotationElement ofArray(String name,
                                     AnnotationValue... values) {
        return of(name, AnnotationValue.ofArray(values));
    }
}

