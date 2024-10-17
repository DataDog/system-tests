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
import jdk.internal.classfile.ClassModel;
import jdk.internal.classfile.constantpool.Utf8Entry;
import jdk.internal.classfile.impl.BoundAttribute;
import jdk.internal.classfile.impl.TemporaryConstantPool;
import jdk.internal.classfile.impl.UnboundAttribute;

/**
 * Models the {@code SourceFile} attribute (@@@ reference needed), which can
 * appear on classes. Delivered as a {@link jdk.internal.classfile.ClassElement} when
 * traversing a {@link ClassModel}.
 */
public sealed interface SourceIDAttribute
        extends Attribute<SourceIDAttribute>, ClassElement
        permits BoundAttribute.BoundSourceIDAttribute, UnboundAttribute.UnboundSourceIDAttribute {

    /**
     * {@return the source id}  The source id is the last modified time of the
     * source file (as reported by the filesystem, in milliseconds) when the
     * classfile is compiled.
     */
    Utf8Entry sourceId();

    /**
     * {@return a {@code SourceID} attribute}
     * @param sourceId the source id
     */
    static SourceIDAttribute of(Utf8Entry sourceId) {
        return new UnboundAttribute.UnboundSourceIDAttribute(sourceId);
    }

    /**
     * {@return a {@code SourceID} attribute}
     * @param sourceId the source id
     */
    static SourceIDAttribute of(String sourceId) {
        return of(TemporaryConstantPool.INSTANCE.utf8Entry(sourceId));
    }
}
