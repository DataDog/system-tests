/*
 * Copyright (c) 2019, 2022, Oracle and/or its affiliates. All rights reserved.
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

package jdk.jfr.internal.consumer;

import java.time.ZoneId;
import java.util.ArrayDeque;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;

import jdk.jfr.EventType;
import jdk.jfr.ValueDescriptor;

public final class ObjectContext {
    private Map<ValueDescriptor, ObjectContext> contextLookup;
    private final TimeConverter timeConverter;
    public final EventType eventType;
    public final List<ValueDescriptor> fields;

    ObjectContext(EventType eventType, List<ValueDescriptor> fields, TimeConverter timeConverter) {
        this.eventType = eventType;
        this.fields = fields;
        this.timeConverter = timeConverter;
    }

    private ObjectContext(Map<ValueDescriptor, ObjectContext> contextLookup, EventType eventType, List<ValueDescriptor> fields, TimeConverter timeConverter) {
        this.eventType = eventType;
        this.contextLookup = contextLookup;
        this.timeConverter = timeConverter;
        this.fields = fields;
    }

    public ObjectContext getInstance(ValueDescriptor descriptor) {
        if (contextLookup == null) {
            // Lazy, only needed when accessing nested structures.
            contextLookup = buildContextLookup(fields);
        }
        return contextLookup.get(descriptor);
    }

    // Create mapping from ValueDescriptor to ObjectContext for all reachable
    // ValueDescriptors.
    public Map<ValueDescriptor, ObjectContext> buildContextLookup(List<ValueDescriptor> fields) {
        Map<ValueDescriptor, ObjectContext> lookup = new IdentityHashMap<>();
        ArrayDeque<ValueDescriptor> q = new ArrayDeque<>(fields);
        while (!q.isEmpty()) {
            ValueDescriptor vd = q.pop();
            if (!lookup.containsKey(vd)) {
                List<ValueDescriptor> children = vd.getFields();
                lookup.put(vd, new ObjectContext(lookup, eventType, children, timeConverter));
                for (ValueDescriptor v : children) {
                    q.add(v);
                }
            }
        }
        return lookup;
    }

    public long convertTimestamp(long ticks) {
        return timeConverter.convertTimestamp(ticks);
    }

    public long convertTimespan(long ticks) {
        return timeConverter.convertTimespan(ticks);
    }

    public ZoneId getZoneOffset() {
        return timeConverter.getZoneOffset();
    }
}
