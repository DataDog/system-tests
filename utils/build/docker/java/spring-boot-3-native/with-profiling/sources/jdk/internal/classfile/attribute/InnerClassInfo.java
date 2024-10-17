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
import java.util.Optional;
import java.util.Set;

import jdk.internal.classfile.constantpool.ClassEntry;
import jdk.internal.classfile.constantpool.Utf8Entry;
import java.lang.reflect.AccessFlag;

import jdk.internal.classfile.impl.TemporaryConstantPool;
import jdk.internal.classfile.impl.UnboundAttribute;
import jdk.internal.classfile.impl.Util;

/**
 * Models a single inner class in the {@link InnerClassesAttribute}.
 */
public sealed interface InnerClassInfo
        permits UnboundAttribute.UnboundInnerClassInfo {

    /**
     * {@return the class described by this inner class description}
     */
    ClassEntry innerClass();

    /**
     * {@return the class or interface of which this class is a member, if it is a
     * member of a class or interface}
     */
    Optional<ClassEntry> outerClass();

    /**
     * {@return the name of the class or interface of which this class is a
     * member, if it is a member of a class or interface}
     */
    Optional<Utf8Entry> innerName();

    /**
     * {@return a bit mask of flags denoting access permissions and properties
     * of the inner class}
     */
    int flagsMask();

    /**
     * {@return a set of flag enums denoting access permissions and properties
     * of the inner class}
     */
    default Set<AccessFlag> flags() {
        return AccessFlag.maskToAccessFlags(flagsMask(), AccessFlag.Location.INNER_CLASS);
    }

    /**
     * {@return whether a specific access flag is set}
     * @param flag the access flag
     */
    default boolean has(AccessFlag flag) {
        return Util.has(AccessFlag.Location.INNER_CLASS, flagsMask(), flag);
    }

    /**
     * {@return an inner class description}
     * @param innerClass the inner class being described
     * @param outerClass the class containing the inner class, if any
     * @param innerName the name of the inner class, if it is not anonymous
     * @param flags the inner class access flags
     */
    static InnerClassInfo of(ClassEntry innerClass, Optional<ClassEntry> outerClass,
                             Optional<Utf8Entry> innerName, int flags) {
        return new UnboundAttribute.UnboundInnerClassInfo(innerClass, outerClass, innerName, flags);
    }

    /**
     * {@return an inner class description}
     * @param innerClass the inner class being described
     * @param outerClass the class containing the inner class, if any
     * @param innerName the name of the inner class, if it is not anonymous
     * @param flags the inner class access flags
     */
    static InnerClassInfo of(ClassDesc innerClass, Optional<ClassDesc> outerClass, Optional<String> innerName, int flags) {
        return new UnboundAttribute.UnboundInnerClassInfo(TemporaryConstantPool.INSTANCE.classEntry(innerClass),
                                                          outerClass.map(TemporaryConstantPool.INSTANCE::classEntry),
                                                          innerName.map(TemporaryConstantPool.INSTANCE::utf8Entry),
                                                          flags);
    }

    /**
     * {@return an inner class description}
     * @param innerClass the inner class being described
     * @param outerClass the class containing the inner class, if any
     * @param innerName the name of the inner class, if it is not anonymous
     * @param flags the inner class access flags
     */
    static InnerClassInfo of(ClassDesc innerClass, Optional<ClassDesc> outerClass, Optional<String> innerName, AccessFlag... flags) {
        return of(innerClass, outerClass, innerName, Util.flagsToBits(AccessFlag.Location.INNER_CLASS, flags));
    }
}
