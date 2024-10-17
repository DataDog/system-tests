/*
 * Copyright (c) 2022, 2023, Oracle and/or its affiliates. All rights reserved.
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

import java.io.InputStream;
import java.lang.constant.ClassDesc;
import java.lang.invoke.MethodHandles;
import java.util.Collection;
import java.util.HashMap;
import java.util.Map;
import java.util.function.Function;
import java.util.function.Supplier;

import jdk.internal.classfile.impl.ClassHierarchyImpl;
import jdk.internal.classfile.impl.ClassHierarchyImpl.ClassLoadingClassHierarchyResolver;
import jdk.internal.classfile.impl.ClassHierarchyImpl.StaticClassHierarchyResolver;
import jdk.internal.classfile.impl.Util;

import static java.lang.constant.ConstantDescs.CD_Object;

/**
 * Provides class hierarchy information for generating correct stack maps
 * during code building.
 */
@FunctionalInterface
public interface ClassHierarchyResolver {

    /**
     * Returns a default instance of {@linkplain ClassHierarchyResolver}
     * that reads from system class loader with
     * {@link ClassLoader#getSystemResourceAsStream(String)} and falls
     * back to reflection if a class is not found.
     */
    static ClassHierarchyResolver defaultResolver() {
        return ClassHierarchyImpl.DEFAULT_RESOLVER;
    }

    /**
     * {@return the {@link ClassHierarchyInfo} for a given class name, or null
     * if the name is unknown to the resolver}
     * @param classDesc descriptor of the class
     */
    ClassHierarchyInfo getClassInfo(ClassDesc classDesc);

    /**
     * Information about a resolved class.
     */
    sealed interface ClassHierarchyInfo permits ClassHierarchyImpl.ClassHierarchyInfoImpl {

        /**
         * Indicates that a class is a declared class, with the specific given super class.
         *
         * @param superClass descriptor of the super class, may be {@code null}
         * @return the info indicating the super class
         */
        static ClassHierarchyInfo ofClass(ClassDesc superClass) {
            return new ClassHierarchyImpl.ClassHierarchyInfoImpl(superClass, false);
        }

        /**
         * Indicates that a class is an interface.
         *
         * @return the info indicating an interface
         */
        static ClassHierarchyInfo ofInterface() {
            return new ClassHierarchyImpl.ClassHierarchyInfoImpl(CD_Object, true);
        }
    }

    /**
     * Chains this {@linkplain ClassHierarchyResolver} with another to be
     * consulted if this resolver does not know about the specified class.
     *
     * @param other the other resolver
     * @return the chained resolver
     */
    default ClassHierarchyResolver orElse(ClassHierarchyResolver other) {
        return new ClassHierarchyResolver() {
            @Override
            public ClassHierarchyInfo getClassInfo(ClassDesc classDesc) {
                var chi = ClassHierarchyResolver.this.getClassInfo(classDesc);
                if (chi == null)
                    return other.getClassInfo(classDesc);
                return chi;
            }
        };
    }

    /**
     * Returns a ClassHierarchyResolver that caches class hierarchy information from this
     * resolver. The returned resolver will not update if delegate resolver returns differently.
     * The thread safety of the returned resolver depends on the thread safety of the map
     * returned by the {@code cacheFactory}.
     *
     * @param cacheFactory the factory for the cache
     * @return the ClassHierarchyResolver with caching
     */
    default ClassHierarchyResolver cached(Supplier<Map<ClassDesc, ClassHierarchyInfo>> cacheFactory) {
        return new ClassHierarchyImpl.CachedClassHierarchyResolver(this, cacheFactory.get());
    }

    /**
     * Returns a ClassHierarchyResolver that caches class hierarchy information from this
     * resolver. The returned resolver will not update if delegate resolver returns differently.
     * The returned resolver is not thread-safe.
     * {@snippet file="PackageSnippets.java" region="lookup-class-hierarchy-resolver"}
     *
     * @return the ClassHierarchyResolver
     */
    default ClassHierarchyResolver cached() {
        record Factory() implements Supplier<Map<ClassDesc, ClassHierarchyInfo>> {
            // uses a record as we cannot declare a local class static
            static final Factory INSTANCE = new Factory();

            @Override
            public Map<ClassDesc, ClassHierarchyInfo> get() {
                return new HashMap<>();
            }
        }
        return cached(Factory.INSTANCE);
    }

    /**
     * Returns a {@linkplain ClassHierarchyResolver} that extracts class hierarchy
     * information from classfiles located by a mapping function. The mapping function
     * should return null if it cannot provide a mapping for a classfile. Any IOException
     * from the provided input stream is rethrown as an UncheckedIOException.
     *
     * @param classStreamResolver maps class descriptors to classfile input streams
     * @return the {@linkplain ClassHierarchyResolver}
     */
    static ClassHierarchyResolver ofResourceParsing(Function<ClassDesc, InputStream> classStreamResolver) {
        return new ClassHierarchyImpl.ResourceParsingClassHierarchyResolver(classStreamResolver);
    }

    /**
     * Returns a {@linkplain ClassHierarchyResolver} that extracts class hierarchy
     * information from classfiles located by a class loader.
     *
     * @param loader the class loader, to find class files
     * @return the {@linkplain ClassHierarchyResolver}
     */
    static ClassHierarchyResolver ofResourceParsing(ClassLoader loader) {
        return ofResourceParsing(new Function<>() {
            @Override
            public InputStream apply(ClassDesc classDesc) {
                return loader.getResourceAsStream(Util.toInternalName(classDesc) + ".class");
            }
        });
    }

    /**
     * Returns a {@linkplain  ClassHierarchyResolver} that extracts class hierarchy
     * information from collections of class hierarchy metadata
     *
     * @param interfaces a collection of classes known to be interfaces
     * @param classToSuperClass a map from classes to their super classes
     * @return the {@linkplain ClassHierarchyResolver}
     */
    static ClassHierarchyResolver of(Collection<ClassDesc> interfaces,
                                            Map<ClassDesc, ClassDesc> classToSuperClass) {
        return new StaticClassHierarchyResolver(interfaces, classToSuperClass);
    }

    /**
     * Returns a ClassHierarchyResolver that extracts class hierarchy information via
     * the Reflection API with a {@linkplain ClassLoader}.
     *
     * @param loader the class loader
     * @return the class hierarchy resolver
     */
    static ClassHierarchyResolver ofClassLoading(ClassLoader loader) {
        return new ClassLoadingClassHierarchyResolver(new Function<>() {
            @Override
            public Class<?> apply(ClassDesc cd) {
                try {
                    return Class.forName(Util.toBinaryName(cd.descriptorString()), false, loader);
                } catch (ClassNotFoundException ex) {
                    return null;
                }
            }
        });
    }

    /**
     * Returns a ClassHierarchyResolver that extracts class hierarchy information via
     * the Reflection API with a {@linkplain MethodHandles.Lookup Lookup}. If the class
     * resolved is inaccessible to the given lookup, it throws {@link
     * IllegalArgumentException} instead of returning {@code null}.
     *
     * @param lookup the lookup, must be able to access classes to resolve
     * @return the class hierarchy resolver
     */
    static ClassHierarchyResolver ofClassLoading(MethodHandles.Lookup lookup) {
        return new ClassLoadingClassHierarchyResolver(new Function<>() {
            @Override
            public Class<?> apply(ClassDesc cd) {
                try {
                    return cd.resolveConstantDesc(lookup);
                } catch (IllegalAccessException ex) {
                    throw new IllegalArgumentException(ex);
                } catch (ReflectiveOperationException ex) {
                    return null;
                }
            }
        });
    }
}
