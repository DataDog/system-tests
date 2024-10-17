/*
 * Copyright (c) 2016, 2022, Oracle and/or its affiliates. All rights reserved.
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
package jdk.jfr.internal.consumer;

import java.io.IOException;
import java.util.ArrayList;

public final class CompositeParser extends Parser {
    final Parser[] parsers;

    public CompositeParser(Parser[] valueParsers) {
        this.parsers = valueParsers;
    }

    @Override
    public Object parse(RecordingInput input) throws IOException {
        final Object[] values = new Object[parsers.length];
        for (int i = 0; i < values.length; i++) {
            values[i] = parsers[i].parse(input);
        }
        return values;
    }

    @Override
    public void skip(RecordingInput input) throws IOException {
        for (int i = 0; i < parsers.length; i++) {
            parsers[i].skip(input);
        }
    }

    @Override
    public Object parseReferences(RecordingInput input) throws IOException {
        return parseReferences(input, parsers);
    }

    static Object parseReferences(RecordingInput input, Parser[] parsers) throws IOException {
        ArrayList<Object> refs = new ArrayList<>(parsers.length);
        for (int i = 0; i < parsers.length; i++) {
            Object ref = parsers[i].parseReferences(input);
            if (ref != null) {
                refs.add(ref);
            }
        }
        if (refs.isEmpty()) {
            return null;
        }
        if (refs.size() == 1) {
            return refs.get(0);
        }
        return refs.toArray();
    }
}