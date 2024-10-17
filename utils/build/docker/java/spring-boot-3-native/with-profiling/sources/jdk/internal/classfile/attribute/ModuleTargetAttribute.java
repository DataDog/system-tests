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
 * Models the {@code ModuleTarget} attribute, which can
 * appear on classes that represent module descriptors.  This is a JDK-specific
 * attribute, which captures constraints on the target platform.
 * Delivered as a {@link jdk.internal.classfile.ClassElement} when
 * traversing the elements of a {@link jdk.internal.classfile.ClassModel}.
 *
 * <p>The specification of the {@code ModuleTarget} attribute is:
 * <pre> {@code
 * TargetPlatform_attribute {
 *   // index to CONSTANT_utf8_info structure in constant pool representing
 *   // the string "ModuleTarget"
 *   u2 attribute_name_index;
 *   u4 attribute_length;
 *
 *   // index to CONSTANT_utf8_info structure with the target platform
 *   u2 target_platform_index;
 * }
 * } </pre>
 */
public sealed interface ModuleTargetAttribute
        extends Attribute<ModuleTargetAttribute>, ClassElement
        permits BoundAttribute.BoundModuleTargetAttribute, UnboundAttribute.UnboundModuleTargetAttribute {

    /**
     * {@return the target platform}
     */
    Utf8Entry targetPlatform();

    /**
     * {@return a {@code ModuleTarget} attribute}
     * @param targetPlatform the target platform
     */
    static ModuleTargetAttribute of(String targetPlatform) {
        return of(TemporaryConstantPool.INSTANCE.utf8Entry(targetPlatform));
    }

    /**
     * {@return a {@code ModuleTarget} attribute}
     * @param targetPlatform the target platform
     */
    static ModuleTargetAttribute of(Utf8Entry targetPlatform) {
        return new UnboundAttribute.UnboundModuleTargetAttribute(targetPlatform);
    }
}
