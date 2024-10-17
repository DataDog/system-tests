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

import jdk.internal.classfile.Attribute;
import jdk.internal.classfile.ClassElement;
import jdk.internal.classfile.constantpool.Utf8Entry;
import jdk.internal.classfile.impl.BoundAttribute;
import jdk.internal.classfile.impl.TemporaryConstantPool;
import jdk.internal.classfile.impl.UnboundAttribute;

/**
 * Models the {@code CompilationID} attribute (@@@ need reference), which can
 * appear on classes and records the compilation time of the class.  Delivered
 * as a {@link jdk.internal.classfile.ClassElement} when traversing the elements of
 * a {@link jdk.internal.classfile.ClassModel}.
 */
public sealed interface CompilationIDAttribute
        extends Attribute<CompilationIDAttribute>, ClassElement
        permits BoundAttribute.BoundCompilationIDAttribute,
                UnboundAttribute.UnboundCompilationIDAttribute {

    /**
     * {@return the compilation ID}  The compilation ID is the value of
     * {@link System#currentTimeMillis()} when the classfile is generated.
     */
    Utf8Entry compilationId();

    /**
     * {@return a {@code CompilationID} attribute}
     * @param id the compilation ID
     */
    static CompilationIDAttribute of(Utf8Entry id) {
        return new UnboundAttribute.UnboundCompilationIDAttribute(id);
    }

    /**
     * {@return a {@code CompilationID} attribute}
     * @param id the compilation ID
     */
    static CompilationIDAttribute of(String id) {
        return new UnboundAttribute.UnboundCompilationIDAttribute(TemporaryConstantPool.INSTANCE.utf8Entry(id));
    }
}
