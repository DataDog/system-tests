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

import jdk.internal.classfile.impl.LabelImpl;

/**
 * A marker for a position within the instructions of a method body.  The
 * assocation between a label's identity and the position it represents is
 * managed by the entity managing the method body (a {@link CodeModel} or {@link
 * CodeBuilder}), not the label itself; this allows the same label to have a
 * meaning both in an existing method (as managed by a {@linkplain CodeModel})
 * and in the transformation of that method (as managed by a {@linkplain
 * CodeBuilder}), while corresponding to different positions in each. When
 * traversing the elements of a {@linkplain CodeModel}, {@linkplain Label}
 * markers will be delivered at the position to which they correspond.  A label
 * can be bound to the current position within a {@linkplain CodeBuilder} via
 * {@link CodeBuilder#labelBinding(Label)} or {@link CodeBuilder#with(ClassfileElement)}.
 */
public sealed interface Label
        permits LabelImpl {
}
