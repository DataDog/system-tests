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

import jdk.internal.classfile.attribute.*;
import jdk.internal.classfile.attribute.ModuleAttribute.ModuleAttributeBuilder;
import jdk.internal.classfile.constantpool.ClassEntry;
import jdk.internal.classfile.constantpool.ModuleEntry;
import jdk.internal.classfile.constantpool.Utf8Entry;
import java.lang.constant.ModuleDesc;
import java.lang.constant.PackageDesc;

import java.lang.constant.ClassDesc;
import java.util.*;

public final class ModuleAttributeBuilderImpl
        implements ModuleAttributeBuilder {

    private ModuleEntry moduleEntry;
    private Utf8Entry moduleVersion;
    private int moduleFlags;

    private final Set<ModuleRequireInfo> requires = new LinkedHashSet<>();
    private final Set<ModuleExportInfo> exports = new LinkedHashSet<>();
    private final Set<ModuleOpenInfo> opens = new LinkedHashSet<>();
    private final Set<ClassEntry> uses = new LinkedHashSet<>();
    private final Set<ModuleProvideInfo> provides = new LinkedHashSet<>();

    public ModuleAttributeBuilderImpl(ModuleEntry moduleName) {
        this.moduleEntry = moduleName;
        this.moduleFlags = 0;
    }

    public ModuleAttributeBuilderImpl(ModuleDesc moduleName) {
        this(TemporaryConstantPool.INSTANCE.moduleEntry(TemporaryConstantPool.INSTANCE.utf8Entry(moduleName.name())));
    }

    @Override
    public ModuleAttribute build() {
        return new UnboundAttribute.UnboundModuleAttribute(moduleEntry, moduleFlags, moduleVersion,
                                                            requires, exports, opens, uses, provides);
    }

    @Override
    public ModuleAttributeBuilder moduleName(ModuleDesc moduleName) {
        Objects.requireNonNull(moduleName);
        moduleEntry = TemporaryConstantPool.INSTANCE.moduleEntry(TemporaryConstantPool.INSTANCE.utf8Entry(moduleName.name()));
        return this;
    }

    @Override
    public ModuleAttributeBuilder moduleFlags(int flags) {
        this.moduleFlags = flags;
        return this;
    }

    @Override
    public ModuleAttributeBuilder moduleVersion(String version) {
        moduleVersion = version == null ? null : TemporaryConstantPool.INSTANCE.utf8Entry(version);
        return this;
    }

    @Override
    public ModuleAttributeBuilder requires(ModuleDesc module, int flags, String version) {
        Objects.requireNonNull(module);
        return requires(ModuleRequireInfo.of(TemporaryConstantPool.INSTANCE.moduleEntry(TemporaryConstantPool.INSTANCE.utf8Entry(module.name())), flags, version == null ? null : TemporaryConstantPool.INSTANCE.utf8Entry(version)));
    }

    @Override
    public ModuleAttributeBuilder requires(ModuleRequireInfo requires) {
        Objects.requireNonNull(requires);
        this.requires.add(requires);
        return this;
    }

    @Override
    public ModuleAttributeBuilder exports(PackageDesc pkge, int flags, ModuleDesc... exportsToModules) {
        Objects.requireNonNull(pkge);
        var exportsTo = new ArrayList<ModuleEntry>(exportsToModules.length);
        for (var e : exportsToModules)
            exportsTo.add(TemporaryConstantPool.INSTANCE.moduleEntry(TemporaryConstantPool.INSTANCE.utf8Entry(e.name())));
        return exports(ModuleExportInfo.of(TemporaryConstantPool.INSTANCE.packageEntry(TemporaryConstantPool.INSTANCE.utf8Entry(pkge.internalName())), flags, exportsTo));
    }

    @Override
    public ModuleAttributeBuilder exports(ModuleExportInfo exports) {
        Objects.requireNonNull(exports);
        this.exports.add(exports);
        return this;
    }

    @Override
    public ModuleAttributeBuilder opens(PackageDesc pkge, int flags, ModuleDesc... opensToModules) {
        Objects.requireNonNull(pkge);
        var opensTo = new ArrayList<ModuleEntry>(opensToModules.length);
        for (var e : opensToModules)
            opensTo.add(TemporaryConstantPool.INSTANCE.moduleEntry(TemporaryConstantPool.INSTANCE.utf8Entry(e.name())));
        return opens(ModuleOpenInfo.of(TemporaryConstantPool.INSTANCE.packageEntry(TemporaryConstantPool.INSTANCE.utf8Entry(pkge.internalName())), flags, opensTo));
    }

    @Override
    public ModuleAttributeBuilder opens(ModuleOpenInfo opens) {
        Objects.requireNonNull(opens);
        this.opens.add(opens);
        return this;
    }

    @Override
    public ModuleAttributeBuilder uses(ClassDesc service) {
        Objects.requireNonNull(service);
        return uses(TemporaryConstantPool.INSTANCE.classEntry(service));
    }

    @Override
    public ModuleAttributeBuilder uses(ClassEntry uses) {
        Objects.requireNonNull(uses);
        this.uses.add(uses);
        return this;
    }

    @Override
    public ModuleAttributeBuilder provides(ClassDesc service, ClassDesc... implClasses) {
        Objects.requireNonNull(service);
        var impls = new ArrayList<ClassEntry>(implClasses.length);
        for (var seq : implClasses)
            impls.add(TemporaryConstantPool.INSTANCE.classEntry(seq));
        return provides(ModuleProvideInfo.of(TemporaryConstantPool.INSTANCE.classEntry(service), impls));
    }

    @Override
    public ModuleAttributeBuilder provides(ModuleProvideInfo provides) {
        Objects.requireNonNull(provides);
        this.provides.add(provides);
        return this;
    }
}
