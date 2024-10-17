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
import java.util.Arrays;
import java.util.List;

import jdk.internal.classfile.constantpool.ClassEntry;
import jdk.internal.classfile.impl.TemporaryConstantPool;
import jdk.internal.classfile.impl.UnboundAttribute;
import jdk.internal.classfile.impl.Util;

/**
 * Models a single "provides" declaration in the {@link jdk.internal.classfile.attribute.ModuleAttribute}.
 */
public sealed interface ModuleProvideInfo
        permits UnboundAttribute.UnboundModuleProvideInfo {

    /**
     * {@return the service interface representing the provided service}
     */
    ClassEntry provides();

    /**
     * {@return the classes providing the service implementation}
     */
    List<ClassEntry> providesWith();

    /**
     * {@return a service provision description}
     * @param provides the service class interface
     * @param providesWith the service class implementations
     */
    static ModuleProvideInfo of(ClassEntry provides,
                                List<ClassEntry> providesWith) {
        return new UnboundAttribute.UnboundModuleProvideInfo(provides, providesWith);
    }

    /**
     * {@return a service provision description}
     * @param provides the service class interface
     * @param providesWith the service class implementations
     */
    static ModuleProvideInfo of(ClassEntry provides,
                                ClassEntry... providesWith) {
        return of(provides, List.of(providesWith));
    }

    /**
     * {@return a service provision description}
     * @param provides the service class interface
     * @param providesWith the service class implementations
     */
    static ModuleProvideInfo of(ClassDesc provides,
                                       List<ClassDesc> providesWith) {
        return of(TemporaryConstantPool.INSTANCE.classEntry(provides), Util.entryList(providesWith));
    }

    /**
     * {@return a service provision description}
     * @param provides the service class interface
     * @param providesWith the service class implementations
     */
    static ModuleProvideInfo of(ClassDesc provides,
                                       ClassDesc... providesWith) {
        // List view, since ref to providesWith is temporary
        return of(provides, Arrays.asList(providesWith));
    }
}
