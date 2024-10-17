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

import java.util.List;
import java.util.Optional;

import jdk.internal.classfile.attribute.CodeAttribute;
import jdk.internal.classfile.impl.BufferedCodeBuilder;
import jdk.internal.classfile.impl.CodeImpl;
import jdk.internal.classfile.instruction.ExceptionCatch;

/**
 * Models the body of a method (the {@code Code} attribute).  The instructions
 * of the method body are accessed via a streaming view (e.g., {@link
 * #elements()}).
 */
public sealed interface CodeModel
        extends CompoundElement<CodeElement>, AttributedElement, MethodElement
        permits CodeAttribute, BufferedCodeBuilder.Model, CodeImpl {

    /**
     * {@return the maximum size of the local variable table}
     */
    int maxLocals();

    /**
     * {@return the maximum size of the operand stack}
     */
    int maxStack();

    /**
     * {@return the enclosing method, if known}
     */
    Optional<MethodModel> parent();

    /**
     * {@return the exception table of the method}  The exception table is also
     * modeled by {@link ExceptionCatch} elements in the streaming view.
     */
    List<ExceptionCatch> exceptionHandlers();
}
