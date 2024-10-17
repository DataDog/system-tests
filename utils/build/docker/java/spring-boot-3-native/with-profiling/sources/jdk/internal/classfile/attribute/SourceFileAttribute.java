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
 * Models the {@code SourceFile} attribute {@jvms 4.7.10}, which
 * can appear on classes. Delivered as a {@link jdk.internal.classfile.ClassElement}
 * when traversing a {@link ClassModel}.
 */
public sealed interface SourceFileAttribute
        extends Attribute<SourceFileAttribute>, ClassElement
        permits BoundAttribute.BoundSourceFileAttribute, UnboundAttribute.UnboundSourceFileAttribute {

    /**
     * {@return the name of the source file from which this class was compiled}
     */
    Utf8Entry sourceFile();

    static SourceFileAttribute of(String sourceFile) {
        return of(TemporaryConstantPool.INSTANCE.utf8Entry(sourceFile));
    }

    static SourceFileAttribute of(Utf8Entry sourceFile) {
        return new UnboundAttribute.UnboundSourceFileAttribute(sourceFile);
    }
}
