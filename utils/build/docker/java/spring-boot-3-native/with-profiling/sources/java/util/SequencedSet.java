/*
 * Copyright (c) 2021, 2023, Oracle and/or its affiliates. All rights reserved.
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

package java.util;

/**
 * A collection that is both a {@link SequencedCollection} and a {@link Set}. As such,
 * it can be thought of either as a {@code Set} that also has a well-defined
 * <a href="SequencedCollection.html#encounter">encounter order</a>, or as a
 * {@code SequencedCollection} that also has unique elements.
 * <p>
 * This interface has the same requirements on the {@code equals} and {@code hashCode}
 * methods as defined by {@link Set#equals Set.equals} and {@link Set#hashCode Set.hashCode}.
 * Thus, a {@code Set} and a {@code SequencedSet} will compare equals if and only
 * if they have equal elements, irrespective of ordering.
 * <p>
 * {@code SequencedSet} defines the {@link #reversed} method, which provides a
 * reverse-ordered <a href="Collection.html#view">view</a> of this set. The only difference
 * from the {@link SequencedCollection#reversed SequencedCollection.reversed} method is
 * that the return type of {@code SequencedSet.reversed} is {@code SequencedSet}.
 * <p>
 * This class is a member of the
 * <a href="{@docRoot}/java.base/java/util/package-summary.html#CollectionsFramework">
 * Java Collections Framework</a>.
 *
 * @param <E> the type of elements in this sequenced set
 * @since 21
 */
public interface SequencedSet<E> extends SequencedCollection<E>, Set<E> {
    /**
     * {@inheritDoc}
     *
     * @return a reverse-ordered view of this collection, as a {@code SequencedSet}
     */
    SequencedSet<E> reversed();
}
