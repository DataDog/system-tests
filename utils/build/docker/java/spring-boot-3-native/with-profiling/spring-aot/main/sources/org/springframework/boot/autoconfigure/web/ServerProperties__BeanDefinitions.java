package org.springframework.boot.autoconfigure.web;

import org.springframework.aot.generate.Generated;
import org.springframework.beans.factory.config.BeanDefinition;
import org.springframework.beans.factory.support.RootBeanDefinition;

/**
 * Bean definitions for {@link ServerProperties}.
 */
@Generated
public class ServerProperties__BeanDefinitions {
  /**
   * Get the bean definition for 'serverProperties'.
   */
  public static BeanDefinition getServerPropertiesBeanDefinition() {
    RootBeanDefinition beanDefinition = new RootBeanDefinition(ServerProperties.class);
    beanDefinition.setInstanceSupplier(ServerProperties::new);
    return beanDefinition;
  }
}
