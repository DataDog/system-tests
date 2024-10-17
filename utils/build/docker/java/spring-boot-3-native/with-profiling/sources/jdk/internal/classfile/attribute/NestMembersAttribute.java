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
 * Models the {@code NestMembers} attribute {@jvms 4.7.29}, which can
 * appear on classes to indicate that this class is the host of a nest.
 * Delivered as a {@link jdk.internal.classfile.ClassElement} when
 * traversing the elements of a {@link jdk.internal.classfile.ClassModel}.
 */
public sealed interface NestMembersAttribute extends Attribute<NestMembersAttribute>, ClassElement
        permits BoundAttribute.BoundNestMembersAttribute, UnboundAttribute.UnboundNestMembersAttribute {

    /**
     * {@return the classes belonging to the nest hosted by this class}
     */
    List<ClassEntry> nestMembers();

    /**
     * {@return a {@code NestMembers} attribute}
     * @param nestMembers the member classes of the nest
     */
    static NestMembersAttribute of(List<ClassEntry> nestMembers) {
        return new UnboundAttribute.UnboundNestMembersAttribute(nestMembers);
    }

    /**
     * {@return a {@code NestMembers} attribute}
     * @param nestMembers the member classes of the nest
     */
    static NestMembersAttribute of(ClassEntry... nestMembers) {
        return of(List.of(nestMembers));
    }

    /**
     * {@return a {@code NestMembers} attribute}
     * @param nestMembers the member classes of the nest
     */
    static NestMembersAttribute ofSymbols(List<ClassDesc> nestMembers) {
        return of(Util.entryList(nestMembers));
    }

    /**
     * {@return a {@code NestMembers} attribute}
     * @param nestMembers the member classes of the nest
     */
    static NestMembersAttribute ofSymbols(ClassDesc... nestMembers) {
        // List view, since ref to nestMembers is temporary
        return ofSymbols(Arrays.asList(nestMembers));
    }
}
