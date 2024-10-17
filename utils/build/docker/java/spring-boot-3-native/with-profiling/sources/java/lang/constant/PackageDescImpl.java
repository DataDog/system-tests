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
package java.lang.constant;

/*
 * Implementation of {@code PackageDesc}
 * @param internalName must have been validated
 */
record PackageDescImpl(String internalName) implements PackageDesc {

    @Override
    public String toString() {
        return String.format("PackageDesc[%s]", name());
    }
}
