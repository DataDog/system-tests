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

import java.util.ArrayList;
import java.util.List;

import jdk.internal.classfile.Attribute;
import jdk.internal.classfile.AttributeMapper;
import jdk.internal.classfile.BufWriter;

public class AttributeHolder {
    private final List<Attribute<?>> attributes = new ArrayList<>();

    public <A extends Attribute<A>> void withAttribute(Attribute<?> a) {
        if (a == null)
            return;

        @SuppressWarnings("unchecked")
        AttributeMapper<A> am = (AttributeMapper<A>) a.attributeMapper();
        if (!am.allowMultiple() && isPresent(am)) {
            remove(am);
        }
        attributes.add(a);
    }

    public int size() {
        return attributes.size();
    }

    public void writeTo(BufWriter buf) {
        buf.writeU2(attributes.size());
        for (Attribute<?> a : attributes)
            a.writeTo(buf);
    }

    boolean isPresent(AttributeMapper<?> am) {
        for (Attribute<?> a : attributes)
            if (a.attributeMapper() == am)
                return true;
        return false;
    }

    private void remove(AttributeMapper<?> am) {
        attributes.removeIf(a -> a.attributeMapper() == am);
    }
}
