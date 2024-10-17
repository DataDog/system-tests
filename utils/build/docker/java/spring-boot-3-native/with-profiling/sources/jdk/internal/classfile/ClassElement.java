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
package jdk.internal.classfile;

import jdk.internal.classfile.attribute.CompilationIDAttribute;
import jdk.internal.classfile.attribute.DeprecatedAttribute;
import jdk.internal.classfile.attribute.EnclosingMethodAttribute;
import jdk.internal.classfile.attribute.InnerClassesAttribute;
import jdk.internal.classfile.attribute.ModuleAttribute;
import jdk.internal.classfile.attribute.ModuleHashesAttribute;
import jdk.internal.classfile.attribute.ModuleMainClassAttribute;
import jdk.internal.classfile.attribute.ModulePackagesAttribute;
import jdk.internal.classfile.attribute.ModuleResolutionAttribute;
import jdk.internal.classfile.attribute.ModuleTargetAttribute;
import jdk.internal.classfile.attribute.NestHostAttribute;
import jdk.internal.classfile.attribute.NestMembersAttribute;
import jdk.internal.classfile.attribute.PermittedSubclassesAttribute;
import jdk.internal.classfile.attribute.RecordAttribute;
import jdk.internal.classfile.attribute.RuntimeInvisibleAnnotationsAttribute;
import jdk.internal.classfile.attribute.RuntimeInvisibleTypeAnnotationsAttribute;
import jdk.internal.classfile.attribute.RuntimeVisibleAnnotationsAttribute;
import jdk.internal.classfile.attribute.RuntimeVisibleTypeAnnotationsAttribute;
import jdk.internal.classfile.attribute.SignatureAttribute;
import jdk.internal.classfile.attribute.SourceDebugExtensionAttribute;
import jdk.internal.classfile.attribute.SourceFileAttribute;
import jdk.internal.classfile.attribute.SourceIDAttribute;
import jdk.internal.classfile.attribute.SyntheticAttribute;
import jdk.internal.classfile.attribute.UnknownAttribute;

/**
 * A {@link ClassfileElement} that can appear when traversing the elements
 * of a {@link ClassModel} or be presented to a {@link ClassBuilder}.
 */
public sealed interface ClassElement extends ClassfileElement
        permits AccessFlags, Superclass, Interfaces, ClassfileVersion,
                FieldModel, MethodModel,
                CustomAttribute, CompilationIDAttribute, DeprecatedAttribute,
                EnclosingMethodAttribute, InnerClassesAttribute,
                ModuleAttribute, ModuleHashesAttribute, ModuleMainClassAttribute,
                ModulePackagesAttribute, ModuleResolutionAttribute, ModuleTargetAttribute,
                NestHostAttribute, NestMembersAttribute, PermittedSubclassesAttribute,
                RecordAttribute,
                RuntimeInvisibleAnnotationsAttribute, RuntimeInvisibleTypeAnnotationsAttribute,
                RuntimeVisibleAnnotationsAttribute, RuntimeVisibleTypeAnnotationsAttribute,
                SignatureAttribute, SourceDebugExtensionAttribute,
                SourceFileAttribute, SourceIDAttribute, SyntheticAttribute, UnknownAttribute {
}
