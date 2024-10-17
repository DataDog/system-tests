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
package jdk.internal.classfile.constantpool;

import java.lang.constant.ConstantDesc;
import java.lang.constant.DynamicCallSiteDesc;

import jdk.internal.classfile.impl.AbstractPoolEntry;
import jdk.internal.classfile.impl.Util;

/**
 * Models a constant pool entry for a dynamic call site.
 */
public sealed interface InvokeDynamicEntry
        extends DynamicConstantPoolEntry
        permits AbstractPoolEntry.InvokeDynamicEntryImpl {

    /**
     * {@return a symbolic descriptor for the dynamic call site}
     */
    default DynamicCallSiteDesc asSymbol() {
        return DynamicCallSiteDesc.of(bootstrap().bootstrapMethod().asSymbol(),
                                      name().stringValue(),
                                      Util.methodTypeSymbol(nameAndType()),
                                      bootstrap().arguments().stream()
                                                 .map(LoadableConstantEntry::constantValue)
                                                 .toArray(ConstantDesc[]::new));
    }
}
