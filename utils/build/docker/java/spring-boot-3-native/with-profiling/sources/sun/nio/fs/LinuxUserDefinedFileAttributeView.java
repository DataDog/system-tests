/*
 * Copyright (c) 2008, 2015, Oracle and/or its affiliates. All rights reserved.
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

package sun.nio.fs;

class LinuxUserDefinedFileAttributeView
    extends UnixUserDefinedFileAttributeView
{

    LinuxUserDefinedFileAttributeView(UnixPath file, boolean followLinks) {
        super(file, followLinks);
    }

    @Override
    protected int maxNameLength() {
        return 255;
    }

}
