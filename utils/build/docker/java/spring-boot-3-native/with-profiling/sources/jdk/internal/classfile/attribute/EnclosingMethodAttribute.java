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
import java.lang.constant.MethodTypeDesc;
import java.util.Optional;

import jdk.internal.classfile.Attribute;
import jdk.internal.classfile.ClassElement;
import jdk.internal.classfile.constantpool.ClassEntry;
import jdk.internal.classfile.constantpool.NameAndTypeEntry;
import jdk.internal.classfile.constantpool.Utf8Entry;
import jdk.internal.classfile.impl.BoundAttribute;
import jdk.internal.classfile.impl.TemporaryConstantPool;
import jdk.internal.classfile.impl.UnboundAttribute;
import jdk.internal.classfile.impl.Util;

/**
 * Models the {@code EnclosingMethod} attribute {@jvms 4.7.7}, which can appear
 * on classes, and indicates that the class is a local or anonymous class.
 * Delivered as a {@link ClassElement} when traversing the elements of a {@link
 * jdk.internal.classfile.ClassModel}.
 */
public sealed interface EnclosingMethodAttribute
        extends Attribute<EnclosingMethodAttribute>, ClassElement
        permits BoundAttribute.BoundEnclosingMethodAttribute,
                UnboundAttribute.UnboundEnclosingMethodAttribute {

    /**
     * {@return the innermost class that encloses the declaration of the current
     * class}
     */
    ClassEntry enclosingClass();

    /**
     * {@return the name and type of the enclosing method, if the class is
     * immediately enclosed by a method or constructor}
     */
    Optional<NameAndTypeEntry> enclosingMethod();

    /**
     * {@return the name of the enclosing method, if the class is
     * immediately enclosed by a method or constructor}
     */
    default Optional<Utf8Entry> enclosingMethodName() {
        return enclosingMethod().map(NameAndTypeEntry::name);
    }

    /**
     * {@return the type of the enclosing method, if the class is
     * immediately enclosed by a method or constructor}
     */
    default Optional<Utf8Entry> enclosingMethodType() {
        return enclosingMethod().map(NameAndTypeEntry::type);
    }

    /**
     * {@return the type of the enclosing method, if the class is
     * immediately enclosed by a method or constructor}
     */
    default Optional<MethodTypeDesc> enclosingMethodTypeSymbol() {
        return enclosingMethod().map(Util::methodTypeSymbol);
    }

    /**
     * {@return an {@code EnclosingMethod} attribute}
     * @param className the class name
     * @param method the name and type of the enclosing method
     */
    static EnclosingMethodAttribute of(ClassEntry className,
                                       Optional<NameAndTypeEntry> method) {
        return new UnboundAttribute.UnboundEnclosingMethodAttribute(className, method.orElse(null));
    }

    /**
     * {@return an {@code EnclosingMethod} attribute}
     * @param className the class name
     * @param methodName the name of the enclosing method
     * @param methodType the type of the enclosing method
     */
    static EnclosingMethodAttribute of(ClassDesc className,
                                       Optional<String> methodName,
                                       Optional<MethodTypeDesc> methodType) {
        return new UnboundAttribute.UnboundEnclosingMethodAttribute(
                        TemporaryConstantPool.INSTANCE.classEntry(className),
                        methodName.isPresent() && methodType.isPresent()
                                ? TemporaryConstantPool.INSTANCE.nameAndTypeEntry(methodName.get(), methodType.get())
                                : null);
    }
}
