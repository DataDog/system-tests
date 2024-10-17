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

import java.util.function.Consumer;
import java.util.function.Supplier;

import jdk.internal.classfile.impl.TransformImpl;

/**
 * A transformation on streams of {@link CodeElement}.
 *
 * @see ClassfileTransform
 */
@FunctionalInterface
public non-sealed interface CodeTransform
        extends ClassfileTransform<CodeTransform, CodeElement, CodeBuilder> {

    /**
     * A code transform that sends all elements to the builder.
     */
    CodeTransform ACCEPT_ALL = new CodeTransform() {
        @Override
        public void accept(CodeBuilder builder, CodeElement element) {
            builder.with(element);
        }
    };

    /**
     * Create a stateful code transform from a {@link Supplier}.  The supplier
     * will be invoked for each transformation.
     *
     * @param supplier a {@link Supplier} that produces a fresh transform object
     *                 for each traversal
     * @return the stateful code transform
     */
    static CodeTransform ofStateful(Supplier<CodeTransform> supplier) {
        return new TransformImpl.SupplierCodeTransform(supplier);
    }

    /**
     * Create a code transform that passes each element through to the builder,
     * and calls the specified function when transformation is complete.
     *
     * @param finisher the function to call when transformation is complete
     * @return the code transform
     */
    static CodeTransform endHandler(Consumer<CodeBuilder> finisher) {
        return new CodeTransform() {
            @Override
            public void accept(CodeBuilder builder, CodeElement element) {
                builder.with(element);
            }

            @Override
            public void atEnd(CodeBuilder builder) {
                finisher.accept(builder);
            }
        };
    }

    @Override
    default CodeTransform andThen(CodeTransform t) {
        return new TransformImpl.ChainedCodeTransform(this, t);
    }

    @Override
    default ResolvedTransform<CodeElement> resolve(CodeBuilder builder) {
        return new TransformImpl.ResolvedTransformImpl<>(e -> accept(builder, e),
                                                         () -> atEnd(builder),
                                                         () -> atStart(builder));
    }
}
