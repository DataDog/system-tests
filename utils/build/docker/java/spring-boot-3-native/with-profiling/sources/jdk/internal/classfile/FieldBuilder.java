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

import jdk.internal.classfile.constantpool.Utf8Entry;
import jdk.internal.classfile.impl.ChainedFieldBuilder;
import jdk.internal.classfile.impl.TerminalFieldBuilder;
import java.lang.reflect.AccessFlag;

import java.util.Optional;
import java.util.function.Consumer;

/**
 * A builder for fields.  Builders are not created directly; they are passed
 * to handlers by methods such as {@link ClassBuilder#withField(Utf8Entry, Utf8Entry, Consumer)}
 * or to field transforms.  The elements of a field can be specified
 * abstractly (by passing a {@link FieldElement} to {@link #with(ClassfileElement)}
 * or concretely by calling the various {@code withXxx} methods.
 *
 * @see FieldTransform
 */
public sealed interface FieldBuilder
        extends ClassfileBuilder<FieldElement, FieldBuilder>
        permits TerminalFieldBuilder, ChainedFieldBuilder {

    /**
     * Sets the field access flags.
     * @param flags the access flags, as a bit mask
     * @return this builder
     */
    default FieldBuilder withFlags(int flags) {
        return with(AccessFlags.ofField(flags));
    }

    /**
     * Sets the field access flags.
     * @param flags the access flags, as a bit mask
     * @return this builder
     */
    default FieldBuilder withFlags(AccessFlag... flags) {
        return with(AccessFlags.ofField(flags));
    }

    /**
     * {@return the {@link FieldModel} representing the field being transformed,
     * if this field builder represents the transformation of some {@link FieldModel}}
     */
    Optional<FieldModel> original();
}
