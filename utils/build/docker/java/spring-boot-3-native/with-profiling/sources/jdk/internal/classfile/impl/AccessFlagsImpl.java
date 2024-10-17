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

import java.util.Set;
import jdk.internal.classfile.AccessFlags;
import java.lang.reflect.AccessFlag;

public final class AccessFlagsImpl extends AbstractElement
        implements AccessFlags {

    private final AccessFlag.Location location;
    private final int flagsMask;
    private Set<AccessFlag> flags;

    public  AccessFlagsImpl(AccessFlag.Location location, AccessFlag... flags) {
        this.location = location;
        this.flagsMask = Util.flagsToBits(location, flags);
        this.flags = Set.of(flags);
    }

    public AccessFlagsImpl(AccessFlag.Location location, int mask) {
        this.location = location;
        this.flagsMask = mask;
    }

    @Override
    public int flagsMask() {
        return flagsMask;
    }

    @Override
    public Set<AccessFlag> flags() {
        if (flags == null)
            flags = AccessFlag.maskToAccessFlags(flagsMask, location);
        return flags;
    }

    @Override
    public void writeTo(DirectClassBuilder builder) {
        builder.setFlags(flagsMask);
    }

    @Override
    public void writeTo(DirectMethodBuilder builder) {
        builder.setFlags(flagsMask);
    }

    @Override
    public void writeTo(DirectFieldBuilder builder) {
        builder.setFlags(flagsMask);
    }

    @Override
    public AccessFlag.Location location() {
        return location;
    }

    @Override
    public boolean has(AccessFlag flag) {
        return Util.has(location, flagsMask, flag);
    }

    @Override
    public String toString() {
        return String.format("AccessFlags[flags=%d]", flagsMask);
    }
}
