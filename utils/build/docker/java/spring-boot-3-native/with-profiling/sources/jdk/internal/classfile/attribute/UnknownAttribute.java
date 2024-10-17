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

/**
 * Models an unknown attribute on a class, method, or field.
 */
public sealed interface UnknownAttribute
        extends Attribute<UnknownAttribute>,
                ClassElement, MethodElement, FieldElement
        permits BoundAttribute.BoundUnknownAttribute {

    /**
     * {@return the uninterpreted contents of the attribute payload}
     */
    byte[] contents();
}
