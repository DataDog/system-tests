package com.datadoghq.springbootnative;

import org.springframework.aot.generate.Generated;
import org.springframework.beans.factory.config.BeanDefinition;
import org.springframework.beans.factory.support.RootBeanDefinition;
import org.springframework.context.annotation.ConfigurationClassUtils;

/**
 * Bean definitions for {@link App}.
 */
@Generated
public class App__BeanDefinitions {
  /**
   * Get the bean definition for 'app'.
   */
  public static BeanDefinition getAppBeanDefinition() {
    RootBeanDefinition beanDefinition = new RootBeanDefinition(App.class);
    beanDefinition.setTargetType(App.class);
    ConfigurationClassUtils.initializeConfigurationClass(App.class);
    beanDefinition.setInstanceSupplier(App$$SpringCGLIB$$0::new);
    return beanDefinition;
  }
}
