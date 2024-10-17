/*
 * Copyright (c) 2009, 2023, Oracle and/or its affiliates. All rights reserved.
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

import java.lang.reflect.AnnotatedElement;
import java.lang.reflect.Modifier;

/**
 * Represents a reference to a resolved Java field. Fields, like methods and types, are resolved
 * through {@link ConstantPool constant pools}.
 */
public interface ResolvedJavaField extends JavaField, ModifiersProvider, AnnotatedElement, Annotated {

    /**
     * {@inheritDoc}
     * <p>
     * Only the {@linkplain Modifier#fieldModifiers() field flags} specified in the JVM
     * specification will be included in the returned mask.
     */
    @Override
    int getModifiers();

    /**
     * Returns the offset of the field relative to the base of its storage container (e.g.,
     * {@code instanceOop} for an instance field or {@code Klass*} for a static field on HotSpot).
     */
    int getOffset();

    default boolean isFinal() {
        return ModifiersProvider.super.isFinalFlagSet();
    }

    /**
     * Determines if this field was injected by the VM. Such a field, for example, is not derived
     * from a class file.
     */
    boolean isInternal();

    /**
     * Determines if this field is a synthetic field as defined by the Java Language Specification.
     */
    boolean isSynthetic();

    /**
     * Returns the {@link ResolvedJavaType} object representing the class or interface that declares
     * this field.
     */
    @Override
    ResolvedJavaType getDeclaringClass();

    /**
     * Gets the value of the {@code ConstantValue} attribute ({@jvms 4.7.2}) associated with this
     * field.
     *
     * @return {@code null} if this field has no {@code ConstantValue} attribute
     * @throws UnsupportedOperationException if this operation is not supported
     */
    default JavaConstant getConstantValue() {
        throw new UnsupportedOperationException();
    }
}
