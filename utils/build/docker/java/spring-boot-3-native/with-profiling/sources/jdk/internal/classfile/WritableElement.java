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

import jdk.internal.classfile.constantpool.ConstantPoolBuilder;
import jdk.internal.classfile.constantpool.PoolEntry;
import jdk.internal.classfile.impl.DirectFieldBuilder;
import jdk.internal.classfile.impl.DirectMethodBuilder;

/**
 * A classfile element that can encode itself as a stream of bytes in the
 * encoding expected by the classfile format.
 *
 * @param <T> the type of the entity
 */
public sealed interface WritableElement<T> extends ClassfileElement
        permits Annotation, AnnotationElement, AnnotationValue, Attribute,
                PoolEntry, BootstrapMethodEntry, FieldModel, MethodModel,
                ConstantPoolBuilder, DirectFieldBuilder, DirectMethodBuilder {
    /**
     * Writes the element to the specified writer
     *
     * @param buf the writer
     */
    void writeTo(BufWriter buf);
}
