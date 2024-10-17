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

import java.util.Optional;

import jdk.internal.classfile.CodeBuilder;
import jdk.internal.classfile.CodeModel;
import jdk.internal.classfile.Label;
import jdk.internal.classfile.constantpool.ConstantPoolBuilder;

public abstract sealed class NonterminalCodeBuilder implements CodeBuilder
    permits ChainedCodeBuilder, BlockCodeBuilderImpl {
    protected final TerminalCodeBuilder terminal;
    protected final CodeBuilder parent;

    public NonterminalCodeBuilder(CodeBuilder parent) {
        this.parent = parent;
        this.terminal = switch (parent) {
            case NonterminalCodeBuilder cb -> cb.terminal;
            case TerminalCodeBuilder cb -> cb;
        };
    }

    @Override
    public int receiverSlot() {
        return terminal.receiverSlot();
    }

    @Override
    public int parameterSlot(int paramNo) {
        return terminal.parameterSlot(paramNo);
    }

    @Override
    public ConstantPoolBuilder constantPool() {
        return terminal.constantPool();
    }

    @Override
    public Optional<CodeModel> original() {
        return terminal.original();
    }

    @Override
    public Label newLabel() {
        return terminal.newLabel();
    }
}
