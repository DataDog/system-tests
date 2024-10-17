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
import jdk.internal.classfile.FieldElement;
import jdk.internal.classfile.MethodElement;
import jdk.internal.classfile.impl.BoundAttribute;
import jdk.internal.classfile.impl.UnboundAttribute;

/**
 * Models the {@code Deprecated} attribute {@jvms 4.7.15}, which can appear on
 * classes, methods, and fields.  Delivered as a  {@link ClassElement},
 * {@link MethodElement}, or  {@link FieldElement} when traversing the elements
 * of a corresponding model.
 */
public sealed interface DeprecatedAttribute
        extends Attribute<DeprecatedAttribute>,
                ClassElement, MethodElement, FieldElement
        permits BoundAttribute.BoundDeprecatedAttribute,
                UnboundAttribute.UnboundDeprecatedAttribute {

    /**
     * {@return a {@code Deprecated} attribute}
     */
    static DeprecatedAttribute of() {
        return new UnboundAttribute.UnboundDeprecatedAttribute();
    }
}
