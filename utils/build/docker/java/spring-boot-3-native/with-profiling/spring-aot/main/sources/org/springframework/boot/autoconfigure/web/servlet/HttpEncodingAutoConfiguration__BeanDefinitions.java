package org.springframework.boot.autoconfigure.web.servlet;

import org.springframework.aot.generate.Generated;
import org.springframework.beans.factory.aot.BeanInstanceSupplier;
import org.springframework.beans.factory.config.BeanDefinition;
import org.springframework.beans.factory.support.RootBeanDefinition;
import org.springframework.boot.autoconfigure.web.ServerProperties;
import org.springframework.web.filter.CharacterEncodingFilter;

/**
 * Bean definitions for {@link HttpEncodingAutoConfiguration}.
 */
@Generated
public class HttpEncodingAutoConfiguration__BeanDefinitions {
  /**
   * Get the bean instance supplier for 'org.springframework.boot.autoconfigure.web.servlet.HttpEncodingAutoConfiguration'.
   */
  private static BeanInstanceSupplier<HttpEncodingAutoConfiguration> getHttpEncodingAutoConfigurationInstanceSupplier(
      ) {
    return BeanInstanceSupplier.<HttpEncodingAutoConfiguration>forConstructor(ServerProperties.class)
            .withGenerator((registeredBean, args) -> new HttpEncodingAutoConfiguration(args.get(0)));
  }

  /**
   * Get the bean definition for 'httpEncodingAutoConfiguration'.
   */
  public static BeanDefinition getHttpEncodingAutoConfigurationBeanDefinition() {
    RootBeanDefinition beanDefinition = new RootBeanDefinition(HttpEncodingAutoConfiguration.class);
    beanDefinition.setInstanceSupplier(getHttpEncodingAutoConfigurationInstanceSupplier());
    return beanDefinition;
  }

  /**
   * Get the bean instance supplier for 'characterEncodingFilter'.
   */
  private static BeanInstanceSupplier<CharacterEncodingFilter> getCharacterEncodingFilterInstanceSupplier(
      ) {
    return BeanInstanceSupplier.<CharacterEncodingFilter>forFactoryMethod(HttpEncodingAutoConfiguration.class, "characterEncodingFilter")
            .withGenerator((registeredBean) -> registeredBean.getBeanFactory().getBean(HttpEncodingAutoConfiguration.class).characterEncodingFilter());
  }

  /**
   * Get the bean definition for 'characterEncodingFilter'.
   */
  public static BeanDefinition getCharacterEncodingFilterBeanDefinition() {
    RootBeanDefinition beanDefinition = new RootBeanDefinition(CharacterEncodingFilter.class);
    beanDefinition.setInstanceSupplier(getCharacterEncodingFilterInstanceSupplier());
    return beanDefinition;
  }

  /**
   * Get the bean instance supplier for 'localeCharsetMappingsCustomizer'.
   */
  private static BeanInstanceSupplier<HttpEncodingAutoConfiguration.LocaleCharsetMappingsCustomizer> getLocaleCharsetMappingsCustomizerInstanceSupplier(
      ) {
    return BeanInstanceSupplier.<HttpEncodingAutoConfiguration.LocaleCharsetMappingsCustomizer>forFactoryMethod(HttpEncodingAutoConfiguration.class, "localeCharsetMappingsCustomizer")
            .withGenerator((registeredBean) -> registeredBean.getBeanFactory().getBean(HttpEncodingAutoConfiguration.class).localeCharsetMappingsCustomizer());
  }

  /**
   * Get the bean definition for 'localeCharsetMappingsCustomizer'.
   */
  public static BeanDefinition getLocaleCharsetMappingsCustomizerBeanDefinition() {
    RootBeanDefinition beanDefinition = new RootBeanDefinition(HttpEncodingAutoConfiguration.LocaleCharsetMappingsCustomizer.class);
    beanDefinition.setInstanceSupplier(getLocaleCharsetMappingsCustomizerInstanceSupplier());
    return beanDefinition;
  }
}
