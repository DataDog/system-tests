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
package jdk.internal.classfile.impl;

import java.util.Objects;

import jdk.internal.classfile.Label;
import jdk.internal.classfile.instruction.LabelTarget;

/**
 * Labels are created with a parent context, which is either a code attribute
 * or a code builder.  A label originating in a code attribute context may be
 * reused in a code builder context, but only labels from a single code
 * attribute may be reused by a single code builder.  Mappings to and from
 * BCI are the responsibility of the context in which it is used; a single
 * word of mutable state is provided, for the exclusive use of the owning
 * context.
 *
 * In practice, this means that labels created in a code attribute can simply
 * store the BCI in the state on creation, and labels created in in a code
 * builder can store the BCI in the state when the label is eventually set; if
 * a code attribute label is reused in a builder, the original BCI can be used
 * as an index into an array.
 */
public final class LabelImpl
        extends AbstractElement
        implements Label, LabelTarget {

    private final LabelContext labelContext;
    private int bci;

        public LabelImpl(LabelContext labelContext, int bci) {
        this.labelContext = Objects.requireNonNull(labelContext);
        this.bci = bci;
    }

    public LabelContext labelContext() {
        return labelContext;
    }

    public int getBCI() {
        return bci;
    }

    public void setBCI(int bci) {
        this.bci = bci;
    }

    @Override
    public Label label() {
        return this;
    }

    @Override
    public void writeTo(DirectCodeBuilder builder) {
        builder.setLabelTarget(this);
    }

    @Override
    public String toString() {
        return String.format("Label[context=%s, bci=%d]", labelContext, bci);
    }
}
