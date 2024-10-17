/*
 * Copyright (c) 2021, Oracle and/or its affiliates. All rights reserved.
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

package java.io;

import java.lang.ref.Reference;
import java.lang.ref.ReferenceQueue;
import java.lang.ref.SoftReference;
import java.util.Objects;

// Maps Class instances to values of type T. Under memory pressure, the
// mapping is released (under soft references GC policy) and would be
// recomputed the next time it is queried. The mapping is bound to the
// lifetime of the class: when the class is unloaded, the mapping is
// removed too.
abstract class ClassCache<T> {

    private static class CacheRef<T> extends SoftReference<T> {
        private final Class<?> type;
        private T strongReferent;

        CacheRef(T referent, ReferenceQueue<T> queue, Class<?> type) {
            super(referent, queue);
            this.type = type;
            this.strongReferent = referent;
        }

        Class<?> getType() {
            return type;
        }

        T getStrong() {
            return strongReferent;
        }

        void clearStrong() {
            strongReferent = null;
        }
    }

    private final ReferenceQueue<T> queue;
    private final ClassValue<CacheRef<T>> map;

    protected abstract T computeValue(Class<?> cl);

    protected ClassCache() {
        queue = new ReferenceQueue<>();
        map = new ClassValue<>() {
            @Override
            protected CacheRef<T> computeValue(Class<?> type) {
                T v = ClassCache.this.computeValue(type);
                Objects.requireNonNull(v);
                return new CacheRef<>(v, queue, type);
            }
        };
    }

    T get(Class<?> cl) {
        while (true) {
            processQueue();

            CacheRef<T> ref = map.get(cl);

            // Case 1: A recently created CacheRef.
            // We might still have strong referent, and can return it.
            // This guarantees progress for at least one thread on every CacheRef.
            // Clear the strong referent before returning to make the cache soft.
            T strongVal = ref.getStrong();
            if (strongVal != null) {
                ref.clearStrong();
                return strongVal;
            }

            // Case 2: Older or recently cleared CacheRef.
            // Check if its soft referent is still available, and return it.
            T val = ref.get();
            if (val != null) {
                return val;
            }

            // Case 3: The reference was cleared.
            // Clear the mapping and retry.
            map.remove(cl);
        }
    }

    private void processQueue() {
        Reference<? extends T> ref;
        while((ref = queue.poll()) != null) {
            CacheRef<? extends T> cacheRef = (CacheRef<? extends T>)ref;
            map.remove(cacheRef.getType());
        }
    }
}
