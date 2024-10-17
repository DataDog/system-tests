/*
 * Copyright (c) 2011, 2022, Oracle and/or its affiliates. All rights reserved.
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

import java.nio.file.Path;
import java.nio.file.LinkOption;
import java.nio.file.spi.FileSystemProvider;
import java.io.IOException;
import java.util.Map;

/**
 * Base implementation class of FileSystemProvider
 */

public abstract class AbstractFileSystemProvider extends FileSystemProvider {
    protected AbstractFileSystemProvider() { }

    /**
     * Splits the given attribute name into the name of an attribute view and
     * the attribute. If the attribute view is not identified then it assumed
     * to be "basic".
     */
    private static String[] split(String attribute) {
        String[] s = new String[2];
        int pos = attribute.indexOf(':');
        if (pos == -1) {
            s[0] = "basic";
            s[1] = attribute;
        } else {
            s[0] = attribute.substring(0, pos++);
            s[1] = (pos == attribute.length()) ? "" : attribute.substring(pos);
        }
        return s;
    }

    /**
     * Gets a DynamicFileAttributeView by name. Returns {@code null} if the
     * view is not available.
     */
    abstract DynamicFileAttributeView getFileAttributeView(Path file,
                                                           String name,
                                                           LinkOption... options);

    @Override
    public final void setAttribute(Path file,
                                   String attribute,
                                   Object value,
                                   LinkOption... options)
        throws IOException
    {
        String[] s = split(attribute);
        if (s[0].isEmpty())
            throw new IllegalArgumentException(attribute);
        DynamicFileAttributeView view = getFileAttributeView(file, s[0], options);
        if (view == null)
            throw new UnsupportedOperationException("View '" + s[0] + "' not available");
        view.setAttribute(s[1], value);
    }

    @Override
    public final Map<String,Object> readAttributes(Path file, String attributes, LinkOption... options)
        throws IOException
    {
        String[] s = split(attributes);
        if (s[0].isEmpty())
            throw new IllegalArgumentException(attributes);
        DynamicFileAttributeView view = getFileAttributeView(file, s[0], options);
        if (view == null)
            throw new UnsupportedOperationException("View '" + s[0] + "' not available");
        return view.readAttributes(s[1].split(","));
    }

    /**
     * Deletes a file. The {@code failIfNotExists} parameters determines if an
     * {@code IOException} is thrown when the file does not exist.
     */
    abstract boolean implDelete(Path file, boolean failIfNotExists) throws IOException;

    @Override
    public final void delete(Path file) throws IOException {
        implDelete(file, true);
    }

    @Override
    public final boolean deleteIfExists(Path file) throws IOException {
        return implDelete(file, false);
    }

    /**
     * Returns a path name as bytes for a Unix domain socket.
     * Different encodings may be used for these names on some platforms.
     * If path is empty, then an empty byte[] is returned.
     */
    public abstract byte[] getSunPathForSocketFile(Path path);
}
