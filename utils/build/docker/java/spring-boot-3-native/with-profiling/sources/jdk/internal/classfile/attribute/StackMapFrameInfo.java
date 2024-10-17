/*
 * Copyright (c) 2023, Oracle and/or its affiliates. All rights reserved.
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

import java.lang.constant.ClassDesc;
import java.util.List;

import jdk.internal.classfile.Label;
import jdk.internal.classfile.constantpool.ClassEntry;
import jdk.internal.classfile.impl.StackMapDecoder;
import jdk.internal.classfile.impl.TemporaryConstantPool;
import static jdk.internal.classfile.Classfile.*;

/**
 * Models stack map frame of {@code StackMapTable} attribute {@jvms 4.7.4}.
 */
public sealed interface StackMapFrameInfo
            permits StackMapDecoder.StackMapFrameImpl {

    int frameType();
    Label target();
    List<VerificationTypeInfo> locals();
    List<VerificationTypeInfo> stack();

    public static StackMapFrameInfo of(Label target,
            List<VerificationTypeInfo> locals,
            List<VerificationTypeInfo> stack) {

        return new StackMapDecoder.StackMapFrameImpl(255, target, locals, stack);
    }

    /**
     * The type of a stack value.
     */
    sealed interface VerificationTypeInfo {
        int tag();
    }

    /**
     * A simple stack value.
     */
    public enum SimpleVerificationTypeInfo implements VerificationTypeInfo {
        ITEM_TOP(VT_TOP),
        ITEM_INTEGER(VT_INTEGER),
        ITEM_FLOAT(VT_FLOAT),
        ITEM_DOUBLE(VT_DOUBLE),
        ITEM_LONG(VT_LONG),
        ITEM_NULL(VT_NULL),
        ITEM_UNINITIALIZED_THIS(VT_UNINITIALIZED_THIS);


        private final int tag;

        SimpleVerificationTypeInfo(int tag) {
            this.tag = tag;
        }

        @Override
        public int tag() {
            return tag;
        }
    }

    /**
     * A stack value for an object type.
     */
    sealed interface ObjectVerificationTypeInfo extends VerificationTypeInfo
            permits StackMapDecoder.ObjectVerificationTypeInfoImpl {

        public static ObjectVerificationTypeInfo of(ClassEntry className) {
            return new StackMapDecoder.ObjectVerificationTypeInfoImpl(className);
        }

        public static ObjectVerificationTypeInfo of(ClassDesc classDesc) {
            return of(TemporaryConstantPool.INSTANCE.classEntry(classDesc));
        }

        /**
         * {@return the class of the value}
         */
        ClassEntry className();

        default ClassDesc classSymbol() {
            return className().asSymbol();
        }
    }

    /**
     * An uninitialized stack value.
     */
    sealed interface UninitializedVerificationTypeInfo extends VerificationTypeInfo
            permits StackMapDecoder.UninitializedVerificationTypeInfoImpl {
        Label newTarget();

        public static UninitializedVerificationTypeInfo of(Label newTarget) {
            return new StackMapDecoder.UninitializedVerificationTypeInfoImpl(newTarget);
        }
    }
}
