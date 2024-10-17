/*
 * Copyright (c) 2014, 2022, Oracle and/or its affiliates. All rights reserved.
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

package com.sun.beans.introspect;

import java.lang.reflect.Method;
import java.util.List;
import java.util.Map;

import com.sun.beans.util.Cache;

import static sun.reflect.misc.ReflectUtil.checkPackageAccess;

public final class ClassInfo {
    private static final ClassInfo DEFAULT = new ClassInfo(null);
    private static final Cache<Class<?>,ClassInfo> CACHE
            = new Cache<Class<?>,ClassInfo>(Cache.Kind.SOFT, Cache.Kind.SOFT) {
        @Override
        public ClassInfo create(Class<?> type) {
            return new ClassInfo(type);
        }
    };

    public static ClassInfo get(Class<?> type) {
        if (type == null) {
            return DEFAULT;
        }
        try {
            checkPackageAccess(type);
            return CACHE.get(type);
        } catch (SecurityException exception) {
            return DEFAULT;
        }
    }

    public static void clear() {
        CACHE.clear();
    }

    public static void remove(Class<?> clz) {
        CACHE.remove(clz);
    }

    private final Object mutex = new Object();
    private final Class<?> type;
    private volatile List<Method> methods;
    private volatile Map<String,PropertyInfo> properties;
    private volatile Map<String,EventSetInfo> eventSets;

    private ClassInfo(Class<?> type) {
        this.type = type;
    }

    public List<Method> getMethods() {
        List<Method> methods = this.methods;
        if (methods == null) {
            synchronized (this.mutex) {
                methods = this.methods;
                if (methods == null) {
                    methods = MethodInfo.get(this.type);
                    this.methods = methods;
                }
            }
        }
        return methods;
    }

    public Map<String,PropertyInfo> getProperties() {
        Map<String, PropertyInfo> properties = this.properties;
        if (properties == null) {
            synchronized (this.mutex) {
                properties = this.properties;
                if (properties == null) {
                    properties = PropertyInfo.get(this.type);
                    this.properties = properties;
                }
            }
        }
        return properties;
    }

    public Map<String,EventSetInfo> getEventSets() {
        Map<String, EventSetInfo> eventSets = this.eventSets;
        if (eventSets == null) {
            synchronized (this.mutex) {
                eventSets = this.eventSets;
                if (eventSets == null) {
                    eventSets = EventSetInfo.get(this.type);
                    this.eventSets = eventSets;
                }
            }
        }
        return eventSets;
    }
}
