package com.datadoghq.springbootnative;

import org.springframework.aot.generate.Generated;
import org.springframework.beans.factory.config.BeanDefinition;
import org.springframework.beans.factory.support.RootBeanDefinition;

/**
 * Bean definitions for {@link IntegrationController}.
 */
@Generated
public class IntegrationController__BeanDefinitions {
  /**
   * Get the bean definition for 'integrationController'.
   */
  public static BeanDefinition getIntegrationControllerBeanDefinition() {
    RootBeanDefinition beanDefinition = new RootBeanDefinition(IntegrationController.class);
    beanDefinition.setInstanceSupplier(IntegrationController::new);
    return beanDefinition;
  }
}
