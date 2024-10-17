package org.springframework.boot.autoconfigure.web.servlet;

import jakarta.servlet.MultipartConfigElement;
import org.springframework.aot.generate.Generated;
import org.springframework.beans.factory.aot.BeanInstanceSupplier;
import org.springframework.beans.factory.config.BeanDefinition;
import org.springframework.beans.factory.support.RootBeanDefinition;
import org.springframework.web.multipart.support.StandardServletMultipartResolver;

/**
 * Bean definitions for {@link MultipartAutoConfiguration}.
 */
@Generated
public class MultipartAutoConfiguration__BeanDefinitions {
  /**
   * Get the bean instance supplier for 'org.springframework.boot.autoconfigure.web.servlet.MultipartAutoConfiguration'.
   */
  private static BeanInstanceSupplier<MultipartAutoConfiguration> getMultipartAutoConfigurationInstanceSupplier(
      ) {
    return BeanInstanceSupplier.<MultipartAutoConfiguration>forConstructor(MultipartProperties.class)
            .withGenerator((registeredBean, args) -> new MultipartAutoConfiguration(args.get(0)));
  }

  /**
   * Get the bean definition for 'multipartAutoConfiguration'.
   */
  public static BeanDefinition getMultipartAutoConfigurationBeanDefinition() {
    RootBeanDefinition beanDefinition = new RootBeanDefinition(MultipartAutoConfiguration.class);
    beanDefinition.setInstanceSupplier(getMultipartAutoConfigurationInstanceSupplier());
    return beanDefinition;
  }

  /**
   * Get the bean instance supplier for 'multipartConfigElement'.
   */
  private static BeanInstanceSupplier<MultipartConfigElement> getMultipartConfigElementInstanceSupplier(
      ) {
    return BeanInstanceSupplier.<MultipartConfigElement>forFactoryMethod(MultipartAutoConfiguration.class, "multipartConfigElement")
            .withGenerator((registeredBean) -> registeredBean.getBeanFactory().getBean(MultipartAutoConfiguration.class).multipartConfigElement());
  }

  /**
   * Get the bean definition for 'multipartConfigElement'.
   */
  public static BeanDefinition getMultipartConfigElementBeanDefinition() {
    RootBeanDefinition beanDefinition = new RootBeanDefinition(MultipartConfigElement.class);
    beanDefinition.setInstanceSupplier(getMultipartConfigElementInstanceSupplier());
    return beanDefinition;
  }

  /**
   * Get the bean instance supplier for 'multipartResolver'.
   */
  private static BeanInstanceSupplier<StandardServletMultipartResolver> getMultipartResolverInstanceSupplier(
      ) {
    return BeanInstanceSupplier.<StandardServletMultipartResolver>forFactoryMethod(MultipartAutoConfiguration.class, "multipartResolver")
            .withGenerator((registeredBean) -> registeredBean.getBeanFactory().getBean(MultipartAutoConfiguration.class).multipartResolver());
  }

  /**
   * Get the bean definition for 'multipartResolver'.
   */
  public static BeanDefinition getMultipartResolverBeanDefinition() {
    RootBeanDefinition beanDefinition = new RootBeanDefinition(StandardServletMultipartResolver.class);
    beanDefinition.setInstanceSupplier(getMultipartResolverInstanceSupplier());
    return beanDefinition;
  }
}
