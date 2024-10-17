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

import java.util.List;

import jdk.internal.classfile.Attribute;
import jdk.internal.classfile.MethodElement;
import jdk.internal.classfile.impl.BoundAttribute;
import jdk.internal.classfile.impl.UnboundAttribute;

/**
 * Models the {@code MethodParameters} attribute {@jvms 4.7.24}, which can
 * appear on methods, and records optional information about the method's
 * parameters.  Delivered as a {@link jdk.internal.classfile.MethodElement} when
 * traversing the elements of a {@link jdk.internal.classfile.MethodModel}.
 */
public sealed interface MethodParametersAttribute
        extends Attribute<MethodParametersAttribute>, MethodElement
        permits BoundAttribute.BoundMethodParametersAttribute,
                UnboundAttribute.UnboundMethodParametersAttribute {

    /**
     * {@return information about the parameters of the method}  The i'th entry
     * in the list correponds to the i'th parameter in the method declaration.
     */
    List<MethodParameterInfo> parameters();

    /**
     * {@return a {@code MethodParameters} attribute}
     * @param parameters the method parameter descriptions
     */
    static MethodParametersAttribute of(List<MethodParameterInfo> parameters) {
        return new UnboundAttribute.UnboundMethodParametersAttribute(parameters);
    }

    /**
     * {@return a {@code MethodParameters} attribute}
     * @param parameters the method parameter descriptions
     */
    static MethodParametersAttribute of(MethodParameterInfo... parameters) {
        return of(List.of(parameters));
    }
}
