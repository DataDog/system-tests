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

import java.util.Collection;
import java.util.function.Function;

import jdk.internal.classfile.AttributeMapper;
import jdk.internal.classfile.ClassHierarchyResolver;
import jdk.internal.classfile.Classfile;
import jdk.internal.classfile.constantpool.Utf8Entry;

import static jdk.internal.classfile.ClassHierarchyResolver.defaultResolver;

public class Options {

    public enum Key {
        GENERATE_STACK_MAPS, PROCESS_DEBUG, PROCESS_LINE_NUMBERS, PROCESS_UNKNOWN_ATTRIBUTES,
        CP_SHARING, FIX_SHORT_JUMPS, PATCH_DEAD_CODE, HIERARCHY_RESOLVER, ATTRIBUTE_MAPPER,
        FILTER_DEAD_LABELS;
    }

    public record OptionValue(Key key, Object value) implements Classfile.Option { }

    public Boolean generateStackmaps = true;
    public Boolean processDebug = true;
    public Boolean processLineNumbers = true;
    public Boolean processUnknownAttributes = true;
    public Boolean cpSharing = true;
    public Boolean fixJumps = true;
    public Boolean patchCode = true;
    public Boolean filterDeadLabels = false;
    public ClassHierarchyResolver classHierarchyResolver = defaultResolver();
    public Function<Utf8Entry, AttributeMapper<?>> attributeMapper = new Function<>() {
        @Override
        public AttributeMapper<?> apply(Utf8Entry k) {
            return null;
        }
    };

    @SuppressWarnings("unchecked")
    public Options(Collection<Classfile.Option> options) {
        for (var o : options) {
            var ov = ((OptionValue)o);
            var v = ov.value();
            switch (ov.key()) {
                case GENERATE_STACK_MAPS -> generateStackmaps = (Boolean) v;
                case PROCESS_DEBUG -> processDebug = (Boolean) v;
                case PROCESS_LINE_NUMBERS -> processLineNumbers = (Boolean) v;
                case PROCESS_UNKNOWN_ATTRIBUTES -> processUnknownAttributes = (Boolean) v;
                case CP_SHARING -> cpSharing = (Boolean) v;
                case FIX_SHORT_JUMPS -> fixJumps = (Boolean) v;
                case PATCH_DEAD_CODE -> patchCode = (Boolean) v;
                case HIERARCHY_RESOLVER -> classHierarchyResolver = (ClassHierarchyResolver) v;
                case ATTRIBUTE_MAPPER -> attributeMapper = (Function<Utf8Entry, AttributeMapper<?>>) v;
                case FILTER_DEAD_LABELS -> filterDeadLabels = (Boolean) v;
            }
        }
    }
}
