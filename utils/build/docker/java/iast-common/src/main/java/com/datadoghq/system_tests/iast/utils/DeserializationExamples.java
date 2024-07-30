package com.datadoghq.system_tests.iast.utils;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.ObjectInputStream;

public class DeserializationExamples {

    public void insecureDeserialization(final InputStream inputStream) {
        try {
            new ObjectInputStream(inputStream);
        } catch (IOException e) {
            // Irrelevant
        }
    }

    public void secureDeserialization(final InputStream inputstrean) {
        try {
            new ObjectInputStream(new ByteArrayInputStream(new byte[0]));
        } catch (IOException e) {
            // Irrelevant
        }
    }
}
