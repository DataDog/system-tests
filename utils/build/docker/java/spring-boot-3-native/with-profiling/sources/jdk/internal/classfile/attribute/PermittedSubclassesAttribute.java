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

import jdk.internal.classfile.Attribute;
import jdk.internal.classfile.ClassElement;
import jdk.internal.classfile.constantpool.ClassEntry;
import jdk.internal.classfile.impl.BoundAttribute;
import jdk.internal.classfile.impl.UnboundAttribute;
import jdk.internal.classfile.impl.Util;

/**
 * Models the {@code PermittedSubclasses} attribute {@jvms 4.7.31}, which can
 * appear on classes to indicate which classes may extend this class.
 * Delivered as a {@link jdk.internal.classfile.ClassElement} when
 * traversing the elements of a {@link jdk.internal.classfile.ClassModel}.
 */
public sealed interface PermittedSubclassesAttribute
        extends Attribute<PermittedSubclassesAttribute>, ClassElement
        permits BoundAttribute.BoundPermittedSubclassesAttribute, UnboundAttribute.UnboundPermittedSubclassesAttribute {

    /**
     * {@return the list of permitted subclasses}
     */
    List<ClassEntry> permittedSubclasses();

    /**
     * {@return a {@code PermittedSubclasses} attribute}
     * @param permittedSubclasses the permitted subclasses
     */
    static PermittedSubclassesAttribute of(List<ClassEntry> permittedSubclasses) {
        return new UnboundAttribute.UnboundPermittedSubclassesAttribute(permittedSubclasses);
    }

    /**
     * {@return a {@code PermittedSubclasses} attribute}
     * @param permittedSubclasses the permitted subclasses
     */
    static PermittedSubclassesAttribute of(ClassEntry... permittedSubclasses) {
        return of(List.of(permittedSubclasses));
    }

    /**
     * {@return a {@code PermittedSubclasses} attribute}
     * @param permittedSubclasses the permitted subclasses
     */
    static PermittedSubclassesAttribute ofSymbols(List<ClassDesc> permittedSubclasses) {
        return of(Util.entryList(permittedSubclasses));
    }

    /**
     * {@return a {@code PermittedSubclasses} attribute}
     * @param permittedSubclasses the permitted subclasses
     */
    static PermittedSubclassesAttribute ofSymbols(ClassDesc... permittedSubclasses) {
        // List view, since ref to nestMembers is temporary
        return ofSymbols(Arrays.asList(permittedSubclasses));
    }
}
