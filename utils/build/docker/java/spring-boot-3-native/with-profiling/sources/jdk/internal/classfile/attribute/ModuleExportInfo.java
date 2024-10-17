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

import java.util.Collection;
import java.util.List;
import java.util.Set;

import jdk.internal.classfile.constantpool.ModuleEntry;
import jdk.internal.classfile.constantpool.PackageEntry;
import java.lang.constant.ModuleDesc;
import java.lang.constant.PackageDesc;
import java.lang.reflect.AccessFlag;

import jdk.internal.classfile.Classfile;
import jdk.internal.classfile.impl.TemporaryConstantPool;
import jdk.internal.classfile.impl.UnboundAttribute;
import jdk.internal.classfile.impl.Util;

/**
 * Models a single "exports" declaration in the {@link jdk.internal.classfile.attribute.ModuleAttribute}.
 */
public sealed interface ModuleExportInfo
        permits UnboundAttribute.UnboundModuleExportInfo {

    /**
     * {@return the exported package}
     */
    PackageEntry exportedPackage();

    /**
     * {@return the flags associated with this export declaration, as a bit mask}
     * Valid flags include {@link Classfile#ACC_SYNTHETIC} and
     * {@link Classfile#ACC_MANDATED}.
     */
    int exportsFlagsMask();

    /**
     * {@return the flags associated with this export declaration, as a set of
     * flag values}
     */
    default Set<AccessFlag> exportsFlags() {
        return AccessFlag.maskToAccessFlags(exportsFlagsMask(), AccessFlag.Location.MODULE_EXPORTS);
    }

    /**
     * {@return the list of modules to which this package is exported, if it is a
     * qualified export}
     */
    List<ModuleEntry> exportsTo();

    /**
     * {@return whether the module has the specified access flag set}
     * @param flag the access flag
     */
    default boolean has(AccessFlag flag) {
        return Util.has(AccessFlag.Location.MODULE_EXPORTS, exportsFlagsMask(), flag);
    }

    /**
     * {@return a module export description}
     * @param exports the exported package
     * @param exportFlags the export flags, as a bitmask
     * @param exportsTo the modules to which this package is exported
     */
    static ModuleExportInfo of(PackageEntry exports, int exportFlags,
                               List<ModuleEntry> exportsTo) {
        return new UnboundAttribute.UnboundModuleExportInfo(exports, exportFlags, exportsTo);
    }

    /**
     * {@return a module export description}
     * @param exports the exported package
     * @param exportFlags the export flags
     * @param exportsTo the modules to which this package is exported
     */
    static ModuleExportInfo of(PackageEntry exports, Collection<AccessFlag> exportFlags,
                               List<ModuleEntry> exportsTo) {
        return of(exports, Util.flagsToBits(AccessFlag.Location.MODULE_EXPORTS, exportFlags), exportsTo);
    }

    /**
     * {@return a module export description}
     * @param exports the exported package
     * @param exportFlags the export flags, as a bitmask
     * @param exportsTo the modules to which this package is exported
     */
    static ModuleExportInfo of(PackageEntry exports,
                               int exportFlags,
                               ModuleEntry... exportsTo) {
        return of(exports, exportFlags, List.of(exportsTo));
    }

    /**
     * {@return a module export description}
     * @param exports the exported package
     * @param exportFlags the export flags
     * @param exportsTo the modules to which this package is exported
     */
    static ModuleExportInfo of(PackageEntry exports,
                               Collection<AccessFlag> exportFlags,
                               ModuleEntry... exportsTo) {
        return of(exports, Util.flagsToBits(AccessFlag.Location.MODULE_EXPORTS, exportFlags), exportsTo);
    }

    /**
     * {@return a module export description}
     * @param exports the exported package
     * @param exportFlags the export flags, as a bitmask
     * @param exportsTo the modules to which this package is exported
     */
    static ModuleExportInfo of(PackageDesc exports, int exportFlags,
                               List<ModuleDesc> exportsTo) {
        return of(TemporaryConstantPool.INSTANCE.packageEntry(TemporaryConstantPool.INSTANCE.utf8Entry(exports.internalName())),
                exportFlags,
                Util.moduleEntryList(exportsTo));
    }

    /**
     * {@return a module export description}
     * @param exports the exported package
     * @param exportFlags the export flags
     * @param exportsTo the modules to which this package is exported
     */
    static ModuleExportInfo of(PackageDesc exports, Collection<AccessFlag> exportFlags,
                               List<ModuleDesc> exportsTo) {
        return of(exports, Util.flagsToBits(AccessFlag.Location.MODULE_EXPORTS, exportFlags), exportsTo);
    }

    /**
     * {@return a module export description}
     * @param exports the exported package
     * @param exportFlags the export flags, as a bitmask
     * @param exportsTo the modules to which this package is exported
     */
    static ModuleExportInfo of(PackageDesc exports,
                               int exportFlags,
                               ModuleDesc... exportsTo) {
        return of(exports, exportFlags, List.of(exportsTo));
    }

    /**
     * {@return a module export description}
     * @param exports the exported package
     * @param exportFlags the export flags
     * @param exportsTo the modules to which this package is exported
     */
    static ModuleExportInfo of(PackageDesc exports,
                               Collection<AccessFlag> exportFlags,
                               ModuleDesc... exportsTo) {
        return of(exports, Util.flagsToBits(AccessFlag.Location.MODULE_EXPORTS, exportFlags), exportsTo);
    }
}
