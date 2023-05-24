package com.datadoghq.system_tests.iast.utils;

import java.security.SecureRandom;
import java.util.Random;

public class WeakRandomnessExamples {

    public String weakRandom() {
        return "This is a weak random value : " + new Random().nextDouble();
    }

    public String secureRandom() {
        return "This is a secure random value : " + new SecureRandom().nextDouble();
    }
}
