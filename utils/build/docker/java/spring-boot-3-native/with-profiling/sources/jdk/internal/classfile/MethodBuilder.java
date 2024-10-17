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

import java.util.Optional;
import java.util.function.Consumer;

import jdk.internal.classfile.constantpool.Utf8Entry;
import jdk.internal.classfile.impl.ChainedMethodBuilder;
import jdk.internal.classfile.impl.TerminalMethodBuilder;
import java.lang.reflect.AccessFlag;

/**
 * A builder for methods.  Builders are not created directly; they are passed
 * to handlers by methods such as {@link ClassBuilder#withMethod(Utf8Entry, Utf8Entry, int, Consumer)}
 * or to method transforms.  The elements of a method can be specified
 * abstractly (by passing a {@link MethodElement} to {@link #with(ClassfileElement)}
 * or concretely by calling the various {@code withXxx} methods.
 *
 * @see MethodTransform
 */
public sealed interface MethodBuilder
        extends ClassfileBuilder<MethodElement, MethodBuilder>
        permits ChainedMethodBuilder, TerminalMethodBuilder {

    /**
     * {@return the {@link MethodModel} representing the method being transformed,
     * if this method builder represents the transformation of some {@link MethodModel}}
     */
    Optional<MethodModel> original();

    /**
     * Sets the method access flags.
     * @param flags the access flags, as a bit mask
     * @return this builder
     */
    default MethodBuilder withFlags(int flags) {
        return with(AccessFlags.ofMethod(flags));
    }

    /**
     * Sets the method access flags.
     * @param flags the access flags, as a bit mask
     * @return this builder
     */
    default MethodBuilder withFlags(AccessFlag... flags) {
        return with(AccessFlags.ofMethod(flags));
    }

    /**
     * Build the method body for this method.
     * @param code a handler receiving a {@link CodeBuilder}
     * @return this builder
     */
    MethodBuilder withCode(Consumer<? super CodeBuilder> code);

    /**
     * Build the method body for this method by transforming the body of another
     * method.
     *
     * @implNote
     * <p>This method behaves as if:
     * {@snippet lang=java :
     *     withCode(b -> b.transformCode(code, transform));
     * }
     *
     * @param code the method body to be transformed
     * @param transform the transform to apply to the method body
     * @return this builder
     */
    MethodBuilder transformCode(CodeModel code, CodeTransform transform);
}
