package org.springframework.boot.web.server;

import org.springframework.aot.generate.Generated;
import org.springframework.beans.factory.config.BeanDefinition;
import org.springframework.beans.factory.support.RootBeanDefinition;

/**
 * Bean definitions for {@link ErrorPageRegistrarBeanPostProcessor}.
 */
@Generated
public class ErrorPageRegistrarBeanPostProcessor__BeanDefinitions {
  /**
   * Get the bean definition for 'errorPageRegistrarBeanPostProcessor'.
   */
  public static BeanDefinition getErrorPageRegistrarBeanPostProcessorBeanDefinition() {
    RootBeanDefinition beanDefinition = new RootBeanDefinition(ErrorPageRegistrarBeanPostProcessor.class);
    beanDefinition.setSynthetic(true);
    beanDefinition.setInstanceSupplier(ErrorPageRegistrarBeanPostProcessor::new);
    return beanDefinition;
  }
}
