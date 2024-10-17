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

import java.lang.constant.ClassDesc;
import jdk.internal.classfile.Attribute;
import jdk.internal.classfile.ClassElement;
import jdk.internal.classfile.constantpool.ClassEntry;
import jdk.internal.classfile.impl.BoundAttribute;
import jdk.internal.classfile.impl.TemporaryConstantPool;
import jdk.internal.classfile.impl.UnboundAttribute;

/**
 * Models the {@code ModuleMainClass} attribute {@jvms 4.7.27}, which can
 * appear on classes that represent module descriptors.
 * Delivered as a {@link jdk.internal.classfile.ClassElement} when
 * traversing the elements of a {@link jdk.internal.classfile.ClassModel}.
 */
public sealed interface ModuleMainClassAttribute
        extends Attribute<ModuleMainClassAttribute>, ClassElement
        permits BoundAttribute.BoundModuleMainClassAttribute, UnboundAttribute.UnboundModuleMainClassAttribute {

    /**
     * {@return main class for this module}
     */
    ClassEntry mainClass();

    /**
     * {@return a {@code ModuleMainClass} attribute}
     * @param mainClass the main class
     */
    static ModuleMainClassAttribute of(ClassEntry mainClass) {
        return new UnboundAttribute.UnboundModuleMainClassAttribute(mainClass);
    }

    /**
     * {@return a {@code ModuleMainClass} attribute}
     * @param mainClass the main class
     */
    static ModuleMainClassAttribute of(ClassDesc mainClass) {
        return new UnboundAttribute.UnboundModuleMainClassAttribute(TemporaryConstantPool.INSTANCE.classEntry(mainClass));
    }
}
