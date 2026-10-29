package com.datadoghq.lambda;

import java.io.File;
import java.lang.reflect.Constructor;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;

public class ScaReachability {

    public static void preloadVulnerableClass() {
        // Force LocalFolderExtractor class load during Lambda initialization so the SCA transformer can
        // register GHSA-hf5p-q87m-crj7 with reached=[] before any HTTP request triggers junrarHit().
        // Without this, the class loads lazily on the first request, so registerCve() and recordHit()
        // fire in the same request with no heartbeat window between them.
        try {
            Class.forName("com.github.junrar.LocalFolderExtractor");
        } catch (Exception ignored) {}
    }

    public static String junrarHit() {
        try {
            Class<?> cls = Class.forName("com.github.junrar.LocalFolderExtractor");
            Constructor<?> ctor = cls.getDeclaredConstructors()[0];
            ctor.setAccessible(true);
            Object instance = ctor.newInstance(new File("/tmp"));
            Class<?> fileHeaderClass = Class.forName("com.github.junrar.rarfile.FileHeader");
            Method method = cls.getDeclaredMethod("createDirectory", fileHeaderClass);
            method.setAccessible(true);
            method.invoke(instance, (Object) null);
        } catch (InvocationTargetException e) {
            if (!(e.getCause() instanceof NullPointerException)) {
                throw new IllegalStateException("Unexpected exception from Junrar", e.getCause());
            }
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException("Failed to invoke Junrar", e);
        }
        return "OK";
    }

    // Keep the reflective invocation in each method: a shared helper would report the same caller
    // symbol for both endpoints, preventing First_Hit_Wins from distinguishing the call sites.
    public static String junrarHitAlt() {
        try {
            Class<?> cls = Class.forName("com.github.junrar.LocalFolderExtractor");
            Constructor<?> ctor = cls.getDeclaredConstructors()[0];
            ctor.setAccessible(true);
            Object instance = ctor.newInstance(new File("/tmp"));
            Class<?> fileHeaderClass = Class.forName("com.github.junrar.rarfile.FileHeader");
            Method method = cls.getDeclaredMethod("createDirectory", fileHeaderClass);
            method.setAccessible(true);
            method.invoke(instance, (Object) null);
        } catch (InvocationTargetException e) {
            if (!(e.getCause() instanceof NullPointerException)) {
                throw new IllegalStateException("Unexpected exception from Junrar", e.getCause());
            }
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException("Failed to invoke Junrar", e);
        }
        return "OK";
    }
}
