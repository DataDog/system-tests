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

/**
 * Bidirectional mapper between the classfile representation of an attribute and
 * how that attribute is modeled in the API.  The attribute mapper is used
 * to parse the classfile representation into a model, and to write the model
 * representation back to a classfile.  For each standard attribute, there is a
 * predefined attribute mapper defined in {@link Attributes}. For nonstandard
 * attributes, clients can define their own {@linkplain AttributeMapper}.
 * Classes that model nonstandard attributes should extend {@link
 * CustomAttribute}.
 */
public interface AttributeMapper<A> {

    /**
     * {@return the name of the attribute}
     */
    String name();

    /**
     * Create an {@link Attribute} instance from a classfile.
     *
     * @param enclosing The class, method, field, or code attribute in which
     *                  this attribute appears
     * @param cf The {@link ClassReader} describing the classfile to read from
     * @param pos The offset into the classfile at which the attribute starts
     * @return the new attribute
     */
    A readAttribute(AttributedElement enclosing, ClassReader cf, int pos);

    /**
     * Write an {@link Attribute} instance to a classfile.
     *
     * @param buf The {@link BufWriter} to which the attribute should be written
     * @param attr The attribute to write
     */
    void writeAttribute(BufWriter buf, A attr);

    /**
     * {@return The earliest classfile version for which this attribute is
     * applicable}
     */
    default int validSince() {
        return Classfile.JAVA_1_VERSION;
    }

    /**
     * {@return whether this attribute may appear more than once in a given location}
     */
    default boolean allowMultiple() {
        return false;
    }
}
