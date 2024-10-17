/*
 * Copyright (c) 2023, Oracle and/or its affiliates. All rights reserved.
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
 */
package jdk.vm.ci.meta;

import java.lang.annotation.Inherited;
import java.util.List;

/**
 * Represents a program element such as a method, constructor, field or class for which annotations
 * may be present.
 */
public interface Annotated {

    /**
     * Constructs the annotations present on this element whose types are in the set composed of {@code type1},
     * {@code type2} and {@code types}. All enum types referenced by the returned annotation are
     * initialized. Class initialization is not triggered for enum types referenced by other
     * annotations of this element.
     *
     * If this element is a class, then {@link Inherited} annotations are included in the set of
     * annotations considered.
     *
     * See {@link java.lang.reflect.AnnotatedElement} for the definition of <em>present</em>.
     *
     * @param type1 an annotation type
     * @param type2 an annotation type
     * @param types more annotation types
     * @return an immutable list of the annotations present on this element that match one of the
     *         given types
     * @throws IllegalArgumentException if any type in the set composed of {@code type1},
     *             {@code type2} and {@code types} is not an annotation interface type
     * @throws UnsupportedOperationException if this operation is not supported
     */
    default List<AnnotationData> getAnnotationData(ResolvedJavaType type1, ResolvedJavaType type2, ResolvedJavaType... types) {
        throw new UnsupportedOperationException();
    }

    /**
     * Constructs the annotation present on this element of type {@code type}.
     *
     * See {@link java.lang.reflect.AnnotatedElement} for the definition of <em>present</em>.
     *
     * @param type the type object corresponding to the annotation interface type
     * @return this element's annotation for the specified annotation type if present on this
     *         element, else null
     * @throws IllegalArgumentException if {@code type} is not an annotation interface type
     * @throws UnsupportedOperationException if this operation is not supported
     */
    default AnnotationData getAnnotationData(ResolvedJavaType type) {
        throw new UnsupportedOperationException();
    }
}
