package com.datadoghq.springbootnative;

import org.springframework.aot.generate.Generated;
import org.springframework.beans.factory.config.BeanDefinition;
import org.springframework.beans.factory.support.RootBeanDefinition;

/**
 * Bean definitions for {@link WebController}.
 */
@Generated
public class WebController__BeanDefinitions {
  /**
   * Get the bean definition for 'webController'.
   */
  public static BeanDefinition getWebControllerBeanDefinition() {
    RootBeanDefinition beanDefinition = new RootBeanDefinition(WebController.class);
    beanDefinition.setInstanceSupplier(WebController::new);
    return beanDefinition;
  }
}
