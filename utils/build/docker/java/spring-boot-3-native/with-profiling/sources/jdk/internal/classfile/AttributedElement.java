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
package jdk.internal.classfile;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

import jdk.internal.classfile.attribute.RecordComponentInfo;
import jdk.internal.classfile.impl.AbstractUnboundModel;

/**
 * A {@link ClassfileElement} describing an entity that has attributes, such
 * as a class, field, method, code attribute, or record component.
 */
public sealed interface AttributedElement extends ClassfileElement
        permits ClassModel, CodeModel, FieldModel, MethodModel,
                RecordComponentInfo, AbstractUnboundModel {

    /**
     * {@return the attributes of this element}
     */
    List<Attribute<?>> attributes();

    /**
     * Finds an attribute by name.
     * @param attr the attribute mapper
     * @param <T> the type of the attribute
     * @return the attribute, or an empty {@linkplain Optional} if the attribute
     * is not present
     */
    default <T extends Attribute<T>> Optional<T> findAttribute(AttributeMapper<T> attr) {
        for (Attribute<?> la : attributes()) {
            if (la.attributeMapper() == attr) {
                @SuppressWarnings("unchecked")
                var res = Optional.of((T) la);
                return res;
            }
        }
        return Optional.empty();
    }

    /**
     * Finds one or more attributes by name.
     * @param attr the attribute mapper
     * @param <T> the type of the attribute
     * @return the attributes, or an empty {@linkplain List} if the attribute
     * is not present
     */
    default <T extends Attribute<T>> List<T> findAttributes(AttributeMapper<T> attr) {
        var list = new ArrayList<T>();
        for (var a : attributes()) {
            if (a.attributeMapper() == attr) {
                @SuppressWarnings("unchecked")
                T t = (T)a;
                list.add(t);
            }
        }
        return list;
    }
}
