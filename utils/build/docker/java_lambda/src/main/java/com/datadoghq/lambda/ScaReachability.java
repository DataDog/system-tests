package com.datadoghq.lambda;

import java.io.File;
import java.lang.reflect.Constructor;
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
    } catch (Exception ignored) {}
    return "OK";
  }

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
    } catch (Exception ignored) {}
    return "OK";
  }
}
