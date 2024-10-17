package org.springframework.boot.web.server;

import org.springframework.aot.generate.Generated;
import org.springframework.beans.factory.config.BeanDefinition;
import org.springframework.beans.factory.support.RootBeanDefinition;

/**
 * Bean definitions for {@link WebServerFactoryCustomizerBeanPostProcessor}.
 */
@Generated
public class WebServerFactoryCustomizerBeanPostProcessor__BeanDefinitions {
  /**
   * Get the bean definition for 'webServerFactoryCustomizerBeanPostProcessor'.
   */
  public static BeanDefinition getWebServerFactoryCustomizerBeanPostProcessorBeanDefinition() {
    RootBeanDefinition beanDefinition = new RootBeanDefinition(WebServerFactoryCustomizerBeanPostProcessor.class);
    beanDefinition.setSynthetic(true);
    beanDefinition.setInstanceSupplier(WebServerFactoryCustomizerBeanPostProcessor::new);
    return beanDefinition;
  }
}
