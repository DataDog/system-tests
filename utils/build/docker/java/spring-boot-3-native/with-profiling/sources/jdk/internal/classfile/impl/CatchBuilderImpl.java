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

import jdk.internal.classfile.CodeBuilder;
import jdk.internal.classfile.Label;
import jdk.internal.classfile.Opcode;

import java.lang.constant.ClassDesc;
import java.lang.constant.ConstantDesc;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;
import java.util.function.Consumer;

public final class CatchBuilderImpl implements CodeBuilder.CatchBuilder {
    final CodeBuilder b;
    final BlockCodeBuilderImpl tryBlock;
    final Label tryCatchEnd;
    final Set<ConstantDesc> catchTypes;
    BlockCodeBuilderImpl catchBlock;

    public CatchBuilderImpl(CodeBuilder b, BlockCodeBuilderImpl tryBlock, Label tryCatchEnd) {
        this.b = b;
        this.tryBlock = tryBlock;
        this.tryCatchEnd = tryCatchEnd;
        this.catchTypes = new HashSet<>();
    }

    @Override
    public CodeBuilder.CatchBuilder catching(ClassDesc exceptionType, Consumer<CodeBuilder.BlockCodeBuilder> catchHandler) {
        return catchingMulti(exceptionType == null ? List.of() : List.of(exceptionType), catchHandler);
    }

    @Override
    public CodeBuilder.CatchBuilder catchingMulti(List<ClassDesc> exceptionTypes, Consumer<CodeBuilder.BlockCodeBuilder> catchHandler) {
        Objects.requireNonNull(exceptionTypes);
        Objects.requireNonNull(catchHandler);

        if (catchBlock == null) {
            if (tryBlock.reachable()) {
                b.branchInstruction(Opcode.GOTO, tryCatchEnd);
            }
        }

        for (var exceptionType : exceptionTypes) {
            if (!catchTypes.add(exceptionType)) {
                throw new IllegalArgumentException("Existing catch block catches exception of type: " + exceptionType);
            }
        }

        // Finish prior catch block
        if (catchBlock != null) {
            catchBlock.end();
            if (catchBlock.reachable()) {
                b.branchInstruction(Opcode.GOTO, tryCatchEnd);
            }
        }

        catchBlock = new BlockCodeBuilderImpl(b, tryCatchEnd);
        Label tryStart = tryBlock.startLabel();
        Label tryEnd = tryBlock.endLabel();
        if (exceptionTypes.isEmpty()) {
            catchBlock.exceptionCatchAll(tryStart, tryEnd, catchBlock.startLabel());
        }
        else {
            for (var exceptionType : exceptionTypes) {
                catchBlock.exceptionCatch(tryStart, tryEnd, catchBlock.startLabel(), exceptionType);
            }
        }
        catchBlock.start();
        catchHandler.accept(catchBlock);

        return this;
    }

    @Override
    public void catchingAll(Consumer<CodeBuilder.BlockCodeBuilder> catchAllHandler) {
        catchingMulti(List.of(), catchAllHandler);
    }

    public void finish() {
        if (catchBlock != null) {
            catchBlock.end();
        }
        b.labelBinding(tryCatchEnd);
    }
}
