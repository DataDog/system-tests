package org.springframework.boot.autoconfigure.http;

import org.springframework.aot.generate.Generated;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.aot.BeanInstanceSupplier;
import org.springframework.beans.factory.config.BeanDefinition;
import org.springframework.beans.factory.support.RootBeanDefinition;
import org.springframework.core.env.Environment;
import org.springframework.http.converter.StringHttpMessageConverter;

/**
 * Bean definitions for {@link HttpMessageConvertersAutoConfiguration}.
 */
@Generated
public class HttpMessageConvertersAutoConfiguration__BeanDefinitions {
  /**
   * Get the bean definition for 'httpMessageConvertersAutoConfiguration'.
   */
  public static BeanDefinition getHttpMessageConvertersAutoConfigurationBeanDefinition() {
    RootBeanDefinition beanDefinition = new RootBeanDefinition(HttpMessageConvertersAutoConfiguration.class);
    beanDefinition.setInstanceSupplier(HttpMessageConvertersAutoConfiguration::new);
    return beanDefinition;
  }

  /**
   * Get the bean instance supplier for 'messageConverters'.
   */
  private static BeanInstanceSupplier<HttpMessageConverters> getMessageConvertersInstanceSupplier(
      ) {
    return BeanInstanceSupplier.<HttpMessageConverters>forFactoryMethod(HttpMessageConvertersAutoConfiguration.class, "messageConverters", ObjectProvider.class)
            .withGenerator((registeredBean, args) -> registeredBean.getBeanFactory().getBean(HttpMessageConvertersAutoConfiguration.class).messageConverters(args.get(0)));
  }

  /**
   * Get the bean definition for 'messageConverters'.
   */
  public static BeanDefinition getMessageConvertersBeanDefinition() {
    RootBeanDefinition beanDefinition = new RootBeanDefinition(HttpMessageConverters.class);
    beanDefinition.setInstanceSupplier(getMessageConvertersInstanceSupplier());
    return beanDefinition;
  }

  /**
   * Bean definitions for {@link HttpMessageConvertersAutoConfiguration.StringHttpMessageConverterConfiguration}.
   */
  @Generated
  public static class StringHttpMessageConverterConfiguration {
    /**
     * Get the bean definition for 'stringHttpMessageConverterConfiguration'.
     */
    public static BeanDefinition getStringHttpMessageConverterConfigurationBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(HttpMessageConvertersAutoConfiguration.StringHttpMessageConverterConfiguration.class);
      beanDefinition.setInstanceSupplier(HttpMessageConvertersAutoConfiguration.StringHttpMessageConverterConfiguration::new);
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'stringHttpMessageConverter'.
     */
    private static BeanInstanceSupplier<StringHttpMessageConverter> getStringHttpMessageConverterInstanceSupplier(
        ) {
      return BeanInstanceSupplier.<StringHttpMessageConverter>forFactoryMethod(HttpMessageConvertersAutoConfiguration.StringHttpMessageConverterConfiguration.class, "stringHttpMessageConverter", Environment.class)
              .withGenerator((registeredBean, args) -> registeredBean.getBeanFactory().getBean(HttpMessageConvertersAutoConfiguration.StringHttpMessageConverterConfiguration.class).stringHttpMessageConverter(args.get(0)));
    }

    /**
     * Get the bean definition for 'stringHttpMessageConverter'.
     */
    public static BeanDefinition getStringHttpMessageConverterBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(StringHttpMessageConverter.class);
      beanDefinition.setInstanceSupplier(getStringHttpMessageConverterInstanceSupplier());
      return beanDefinition;
    }
  }
}
