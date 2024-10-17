package org.springframework.boot.autoconfigure.web.client;

import org.springframework.aot.generate.Generated;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.aot.BeanInstanceSupplier;
import org.springframework.beans.factory.config.BeanDefinition;
import org.springframework.beans.factory.support.RootBeanDefinition;
import org.springframework.boot.web.client.RestTemplateBuilder;

/**
 * Bean definitions for {@link RestTemplateAutoConfiguration}.
 */
@Generated
public class RestTemplateAutoConfiguration__BeanDefinitions {
  /**
   * Get the bean definition for 'restTemplateAutoConfiguration'.
   */
  public static BeanDefinition getRestTemplateAutoConfigurationBeanDefinition() {
    RootBeanDefinition beanDefinition = new RootBeanDefinition(RestTemplateAutoConfiguration.class);
    beanDefinition.setInstanceSupplier(RestTemplateAutoConfiguration::new);
    return beanDefinition;
  }

  /**
   * Get the bean instance supplier for 'restTemplateBuilderConfigurer'.
   */
  private static BeanInstanceSupplier<RestTemplateBuilderConfigurer> getRestTemplateBuilderConfigurerInstanceSupplier(
      ) {
    return BeanInstanceSupplier.<RestTemplateBuilderConfigurer>forFactoryMethod(RestTemplateAutoConfiguration.class, "restTemplateBuilderConfigurer", ObjectProvider.class, ObjectProvider.class, ObjectProvider.class)
            .withGenerator((registeredBean, args) -> registeredBean.getBeanFactory().getBean(RestTemplateAutoConfiguration.class).restTemplateBuilderConfigurer(args.get(0), args.get(1), args.get(2)));
  }

  /**
   * Get the bean definition for 'restTemplateBuilderConfigurer'.
   */
  public static BeanDefinition getRestTemplateBuilderConfigurerBeanDefinition() {
    RootBeanDefinition beanDefinition = new RootBeanDefinition(RestTemplateBuilderConfigurer.class);
    beanDefinition.setLazyInit(true);
    beanDefinition.setInstanceSupplier(getRestTemplateBuilderConfigurerInstanceSupplier());
    return beanDefinition;
  }

  /**
   * Get the bean instance supplier for 'restTemplateBuilder'.
   */
  private static BeanInstanceSupplier<RestTemplateBuilder> getRestTemplateBuilderInstanceSupplier(
      ) {
    return BeanInstanceSupplier.<RestTemplateBuilder>forFactoryMethod(RestTemplateAutoConfiguration.class, "restTemplateBuilder", RestTemplateBuilderConfigurer.class)
            .withGenerator((registeredBean, args) -> registeredBean.getBeanFactory().getBean(RestTemplateAutoConfiguration.class).restTemplateBuilder(args.get(0)));
  }

  /**
   * Get the bean definition for 'restTemplateBuilder'.
   */
  public static BeanDefinition getRestTemplateBuilderBeanDefinition() {
    RootBeanDefinition beanDefinition = new RootBeanDefinition(RestTemplateBuilder.class);
    beanDefinition.setLazyInit(true);
    beanDefinition.setInstanceSupplier(getRestTemplateBuilderInstanceSupplier());
    return beanDefinition;
  }
}
