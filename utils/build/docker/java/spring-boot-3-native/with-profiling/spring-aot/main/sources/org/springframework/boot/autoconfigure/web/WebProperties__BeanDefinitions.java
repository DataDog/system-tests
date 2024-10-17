package org.springframework.boot.autoconfigure.web;

import org.springframework.aot.generate.Generated;
import org.springframework.beans.factory.config.BeanDefinition;
import org.springframework.beans.factory.support.RootBeanDefinition;

/**
 * Bean definitions for {@link WebProperties}.
 */
@Generated
public class WebProperties__BeanDefinitions {
  /**
   * Get the bean definition for 'webProperties'.
   */
  public static BeanDefinition getWebPropertiesBeanDefinition() {
    RootBeanDefinition beanDefinition = new RootBeanDefinition(WebProperties.class);
    beanDefinition.setInstanceSupplier(WebProperties::new);
    return beanDefinition;
  }
}
