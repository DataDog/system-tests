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

import jdk.internal.classfile.constantpool.ModuleEntry;
import java.lang.constant.ModuleDesc;
import jdk.internal.classfile.impl.TemporaryConstantPool;
import jdk.internal.classfile.impl.UnboundAttribute;

/**
 * Models hash information for a single module in the {@link jdk.internal.classfile.attribute.ModuleHashesAttribute}.
 */
public sealed interface ModuleHashInfo
        permits UnboundAttribute.UnboundModuleHashInfo {

    /**
     * {@return the name of the related module}
     */
    ModuleEntry moduleName();

    /**
     * {@return the hash of the related module}
     */
    byte[] hash();

    /**
     * {@return a module hash description}
     * @param moduleName the module name
     * @param hash the hash value
     */
    static ModuleHashInfo of(ModuleEntry moduleName, byte[] hash) {
        return new UnboundAttribute.UnboundModuleHashInfo(moduleName, hash);
    }

    /**
     * {@return a module hash description}
     * @param moduleDesc the module name
     * @param hash the hash value
     */
    static ModuleHashInfo of(ModuleDesc moduleDesc, byte[] hash) {
        return new UnboundAttribute.UnboundModuleHashInfo(TemporaryConstantPool.INSTANCE.moduleEntry(TemporaryConstantPool.INSTANCE.utf8Entry(moduleDesc.name())), hash);
    }
}
