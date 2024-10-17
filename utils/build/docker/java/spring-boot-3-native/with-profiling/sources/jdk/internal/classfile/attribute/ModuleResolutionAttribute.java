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
 * Models the {@code ModuleResolution} attribute, which can
 * appear on classes that represent module descriptors.  This is a JDK-specific
 *  * attribute, which captures resolution metadata for modules.
 * Delivered as a {@link jdk.internal.classfile.ClassElement} when
 * traversing the elements of a {@link jdk.internal.classfile.ClassModel}.
 *
 *  <p>The specification of the {@code ModuleResolution} attribute is:
 * <pre> {@code
 *  ModuleResolution_attribute {
 *    u2 attribute_name_index;    // "ModuleResolution"
 *    u4 attribute_length;        // 2
 *    u2 resolution_flags;
 *
 *  The value of the resolution_flags item is a mask of flags used to denote
 *  properties of module resolution. The flags are as follows:
 *
 *   // Optional
 *   0x0001 (DO_NOT_RESOLVE_BY_DEFAULT)
 *
 *   // At most one of:
 *   0x0002 (WARN_DEPRECATED)
 *   0x0004 (WARN_DEPRECATED_FOR_REMOVAL)
 *   0x0008 (WARN_INCUBATING)
 *  }
 * } </pre>
 */
public sealed interface ModuleResolutionAttribute
        extends Attribute<ModuleResolutionAttribute>, ClassElement
        permits BoundAttribute.BoundModuleResolutionAttribute, UnboundAttribute.UnboundModuleResolutionAttribute {

    /**
     *  The value of the resolution_flags item is a mask of flags used to denote
     *  properties of module resolution. The flags are as follows:
     *
     *   // Optional
     *   0x0001 (DO_NOT_RESOLVE_BY_DEFAULT)
     *
     *   // At most one of:
     *   0x0002 (WARN_DEPRECATED)
     *   0x0004 (WARN_DEPRECATED_FOR_REMOVAL)
     *   0x0008 (WARN_INCUBATING)
     */
    int resolutionFlags();

    /**
     * {@return a {@code ModuleResolution} attribute}
     * @param resolutionFlags the resolution falgs
     */
    static ModuleResolutionAttribute of(int resolutionFlags) {
        return new UnboundAttribute.UnboundModuleResolutionAttribute(resolutionFlags);
    }
}
