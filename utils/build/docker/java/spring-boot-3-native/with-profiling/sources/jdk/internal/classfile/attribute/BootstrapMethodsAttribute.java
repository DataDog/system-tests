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
import jdk.internal.classfile.BootstrapMethodEntry;
import jdk.internal.classfile.constantpool.ConstantPool;
import jdk.internal.classfile.impl.BoundAttribute;
import jdk.internal.classfile.impl.UnboundAttribute;

/**
 * Models the {@code BootstrapMethods} attribute {@jvms 4.7.23}, which serves as
 * an extension to the constant pool of a classfile.  Elements of the bootstrap
 * method table are accessed through {@link ConstantPool}.
 */
public sealed interface BootstrapMethodsAttribute
        extends Attribute<BootstrapMethodsAttribute>
        permits BoundAttribute.BoundBootstrapMethodsAttribute,
                UnboundAttribute.EmptyBootstrapAttribute {

    /**
     * {@return the elements of the bootstrap method table}
     */
    List<BootstrapMethodEntry> bootstrapMethods();

    /**
     * {@return the size of the bootstrap methods table}.  Calling this method
     * does not necessarily inflate the entire table.
     */
    int bootstrapMethodsSize();

    // No factories; BMA is generated as part of constant pool
}
