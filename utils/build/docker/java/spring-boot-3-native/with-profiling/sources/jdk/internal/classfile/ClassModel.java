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
import java.util.function.Consumer;

import jdk.internal.classfile.constantpool.ClassEntry;
import jdk.internal.classfile.constantpool.ConstantPool;
import jdk.internal.classfile.impl.ClassImpl;
import jdk.internal.classfile.impl.verifier.VerifierImpl;

/**
 * Models a classfile.  The contents of the classfile can be traversed via
 * a streaming view (e.g., {@link #elements()}), or via random access (e.g.,
 * {@link #flags()}), or by freely mixing the two.
 */
public sealed interface ClassModel
        extends CompoundElement<ClassElement>, AttributedElement
        permits ClassImpl {

    /**
     * {@return the constant pool for this class}
     */
    ConstantPool constantPool();

    /** {@return the access flags} */
    AccessFlags flags();

    /** {@return the constant pool entry describing the name of this class} */
    ClassEntry thisClass();

    /** {@return the major classfile version} */
    int majorVersion();

    /** {@return the minor classfile version} */
    int minorVersion();

    /** {@return the fields of this class} */
    List<FieldModel> fields();

    /** {@return the methods of this class} */
    List<MethodModel> methods();

    /** {@return the superclass of this class, if there is one} */
    Optional<ClassEntry> superclass();

    /** {@return the interfaces implemented by this class} */
    List<ClassEntry> interfaces();

    /**
     * Transform this classfile into a new classfile with the aid of a
     * {@link ClassTransform}.  The transform will receive each element of
     * this class, as well as a {@link ClassBuilder} for building the new class.
     * The transform is free to preserve, remove, or replace elements as it
     * sees fit.
     *
     * @implNote
     * <p>This method behaves as if:
     * {@snippet lang=java :
     *     Classfile.build(thisClass(), ConstantPoolBuilder.of(this),
     *                     b -> b.transform(this, transform));
     * }
     *
     * @param transform the transform
     * @return the bytes of the new class
     */
    byte[] transform(ClassTransform transform);

    /** {@return whether this class is a module descriptor} */
    boolean isModuleInfo();

    /**
     * Verify this classfile.  Any verification errors found will be returned.
     *
     * @param debugOutput handler to receive debug information
     * @return a list of verification errors, or an empty list if no errors are
     * found
     */
    default List<VerifyError> verify(Consumer<String> debugOutput) {
        return VerifierImpl.verify(this, debugOutput);
    }

    /**
     * Verify this classfile.  Any verification errors found will be returned.
     *
     * @param debugOutput handler to receive debug information
     * @param classHierarchyResolver class hierarchy resolver to provide
     *                               additional information about the class hiearchy
     * @return a list of verification errors, or an empty list if no errors are
     * found
     */
    default List<VerifyError> verify(ClassHierarchyResolver classHierarchyResolver,
                                     Consumer<String> debugOutput) {
        return VerifierImpl.verify(this, classHierarchyResolver, debugOutput);
    }
}
