package org.springframework.boot.autoconfigure.web.servlet;

import java.util.List;
import org.springframework.aot.generate.Generated;
import org.springframework.beans.factory.aot.AutowiredMethodArgumentsResolver;
import org.springframework.beans.factory.support.RegisteredBean;

/**
 * Autowiring for {@link WebMvcAutoConfiguration.EnableWebMvcConfiguration}.
 */
@Generated
public class WebMvcAutoConfiguration_EnableWebMvcConfiguration__Autowiring {
  /**
   * Apply the autowiring.
   */
  public static WebMvcAutoConfiguration.EnableWebMvcConfiguration apply(
      RegisteredBean registeredBean, WebMvcAutoConfiguration.EnableWebMvcConfiguration instance) {
    AutowiredMethodArgumentsResolver.forMethod("setConfigurers", List.class).resolve(registeredBean, args -> instance.setConfigurers(args.get(0)));
    return instance;
  }
}
