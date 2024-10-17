package org.springframework.boot.autoconfigure.http;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.aot.generate.Generated;
import org.springframework.beans.factory.aot.BeanInstanceSupplier;
import org.springframework.beans.factory.config.BeanDefinition;
import org.springframework.beans.factory.support.RootBeanDefinition;
import org.springframework.http.converter.json.MappingJackson2HttpMessageConverter;

/**
 * Bean definitions for {@link JacksonHttpMessageConvertersConfiguration}.
 */
@Generated
public class JacksonHttpMessageConvertersConfiguration__BeanDefinitions {
  /**
   * Get the bean definition for 'jacksonHttpMessageConvertersConfiguration'.
   */
  public static BeanDefinition getJacksonHttpMessageConvertersConfigurationBeanDefinition() {
    RootBeanDefinition beanDefinition = new RootBeanDefinition(JacksonHttpMessageConvertersConfiguration.class);
    beanDefinition.setInstanceSupplier(JacksonHttpMessageConvertersConfiguration::new);
    return beanDefinition;
  }

  /**
   * Bean definitions for {@link JacksonHttpMessageConvertersConfiguration.MappingJackson2HttpMessageConverterConfiguration}.
   */
  @Generated
  public static class MappingJackson2HttpMessageConverterConfiguration {
    /**
     * Get the bean definition for 'mappingJackson2HttpMessageConverterConfiguration'.
     */
    public static BeanDefinition getMappingJacksonHttpMessageConverterConfigurationBeanDefinition(
        ) {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(JacksonHttpMessageConvertersConfiguration.MappingJackson2HttpMessageConverterConfiguration.class);
      beanDefinition.setInstanceSupplier(JacksonHttpMessageConvertersConfiguration.MappingJackson2HttpMessageConverterConfiguration::new);
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'mappingJackson2HttpMessageConverter'.
     */
    private static BeanInstanceSupplier<MappingJackson2HttpMessageConverter> getMappingJacksonHttpMessageConverterInstanceSupplier(
        ) {
      return BeanInstanceSupplier.<MappingJackson2HttpMessageConverter>forFactoryMethod(JacksonHttpMessageConvertersConfiguration.MappingJackson2HttpMessageConverterConfiguration.class, "mappingJackson2HttpMessageConverter", ObjectMapper.class)
              .withGenerator((registeredBean, args) -> registeredBean.getBeanFactory().getBean(JacksonHttpMessageConvertersConfiguration.MappingJackson2HttpMessageConverterConfiguration.class).mappingJackson2HttpMessageConverter(args.get(0)));
    }

    /**
     * Get the bean definition for 'mappingJackson2HttpMessageConverter'.
     */
    public static BeanDefinition getMappingJacksonHttpMessageConverterBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(MappingJackson2HttpMessageConverter.class);
      beanDefinition.setInstanceSupplier(getMappingJacksonHttpMessageConverterInstanceSupplier());
      return beanDefinition;
    }
  }
}
