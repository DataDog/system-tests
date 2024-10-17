package org.springframework.boot.autoconfigure.web.servlet;

import org.springframework.aot.generate.Generated;
import org.springframework.beans.factory.config.BeanDefinition;
import org.springframework.beans.factory.support.RootBeanDefinition;

/**
 * Bean definitions for {@link MultipartProperties}.
 */
@Generated
public class MultipartProperties__BeanDefinitions {
  /**
   * Get the bean definition for 'multipartProperties'.
   */
  public static BeanDefinition getMultipartPropertiesBeanDefinition() {
    RootBeanDefinition beanDefinition = new RootBeanDefinition(MultipartProperties.class);
    beanDefinition.setInstanceSupplier(MultipartProperties::new);
    return beanDefinition;
  }
}
