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

import java.util.Optional;
import java.util.Set;

import jdk.internal.classfile.constantpool.Utf8Entry;
import java.lang.reflect.AccessFlag;
import jdk.internal.classfile.Classfile;
import jdk.internal.classfile.impl.TemporaryConstantPool;
import jdk.internal.classfile.impl.UnboundAttribute;
import jdk.internal.classfile.impl.Util;

/**
 * Models a single method parameter in the {@link MethodParametersAttribute}.
 */
public sealed interface MethodParameterInfo
        permits UnboundAttribute.UnboundMethodParameterInfo {
    /**
     * The name of the method parameter, if there is one.
     *
     * @return the parameter name, if it has one
     */
    Optional<Utf8Entry> name();

    /**
     * Parameter access flags for this parameter, as a bit mask.  Valid
     * parameter flags include {@link Classfile#ACC_FINAL},
     * {@link Classfile#ACC_SYNTHETIC}, and {@link Classfile#ACC_MANDATED}.
     *
     * @return the access flags, as a bit mask
     */
    int flagsMask();

    /**
     * Parameter access flags for this parameter.
     *
     * @return the access flags, as a bit mask
     */
    default Set<AccessFlag> flags() {
        return AccessFlag.maskToAccessFlags(flagsMask(), AccessFlag.Location.METHOD_PARAMETER);
    }

    /**
     * {@return whether the method parameter has a specific flag set}
     * @param flag the method parameter flag
     */
    default boolean has(AccessFlag flag) {
        return Util.has(AccessFlag.Location.METHOD_PARAMETER, flagsMask(), flag);
    }

    /**
     * {@return a method parameter description}
     * @param name the method parameter name
     * @param flags the method parameter access flags
     */
    static MethodParameterInfo of(Optional<Utf8Entry> name, int flags) {
        return new UnboundAttribute.UnboundMethodParameterInfo(name, flags);
    }

    /**
     * {@return a method parameter description}
     * @param name the method parameter name
     * @param flags the method parameter access flags
     */
    static MethodParameterInfo of(Optional<String> name, AccessFlag... flags) {
        return of(name.map(TemporaryConstantPool.INSTANCE::utf8Entry), Util.flagsToBits(AccessFlag.Location.METHOD_PARAMETER, flags));
    }

    /**
     * {@return a method parameter description}
     * @param name the method parameter name
     * @param flags the method parameter access flags
     */
    static MethodParameterInfo ofParameter(Optional<String> name, int flags) {
        return of(name.map(TemporaryConstantPool.INSTANCE::utf8Entry), flags);
    }
}
