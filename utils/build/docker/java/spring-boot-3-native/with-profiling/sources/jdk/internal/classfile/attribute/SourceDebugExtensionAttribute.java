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
import jdk.internal.classfile.impl.BoundAttribute;
import jdk.internal.classfile.impl.UnboundAttribute;

/**
 * SourceDebugExtensionAttribute.
 */
public sealed interface SourceDebugExtensionAttribute
        extends Attribute<SourceDebugExtensionAttribute>, ClassElement
        permits BoundAttribute.BoundSourceDebugExtensionAttribute, UnboundAttribute.UnboundSourceDebugExtensionAttribute {

    /**
     * {@return the debug extension payload}
     */
    byte[] contents();

    /**
     * {@return a {@code SourceDebugExtension} attribute}
     * @param contents the extension contents
     */
    static SourceDebugExtensionAttribute of(byte[] contents) {
        return new UnboundAttribute.UnboundSourceDebugExtensionAttribute(contents);
    }
}
