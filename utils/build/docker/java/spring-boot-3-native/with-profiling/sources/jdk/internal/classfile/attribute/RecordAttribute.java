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
import jdk.internal.classfile.impl.BoundAttribute;
import jdk.internal.classfile.impl.UnboundAttribute;

/**
 * Models the {@code Record} attribute {@jvms 4.7.30}, which can
 * appear on classes to indicate that this class is a record class.
 * Delivered as a {@link jdk.internal.classfile.ClassElement} when
 * traversing the elements of a {@link jdk.internal.classfile.ClassModel}.
 */
public sealed interface RecordAttribute extends Attribute<RecordAttribute>, ClassElement
        permits BoundAttribute.BoundRecordAttribute, UnboundAttribute.UnboundRecordAttribute {

    /**
     * {@return the components of this record class}
     */
    List<RecordComponentInfo> components();

    /**
     * {@return a {@code Record} attribute}
     * @param components the record components
     */
    static RecordAttribute of(List<RecordComponentInfo> components) {
        return new UnboundAttribute.UnboundRecordAttribute(components);
    }

    /**
     * {@return a {@code Record} attribute}
     * @param components the record components
     */
    static RecordAttribute of(RecordComponentInfo... components) {
        return of(List.of(components));
    }
}
