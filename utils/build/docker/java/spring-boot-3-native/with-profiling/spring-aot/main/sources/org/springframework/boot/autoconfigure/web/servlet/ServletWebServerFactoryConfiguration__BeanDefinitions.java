package org.springframework.boot.autoconfigure.web.servlet;

import org.springframework.aot.generate.Generated;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.aot.BeanInstanceSupplier;
import org.springframework.beans.factory.config.BeanDefinition;
import org.springframework.beans.factory.support.RootBeanDefinition;
import org.springframework.boot.web.embedded.tomcat.TomcatServletWebServerFactory;

/**
 * Bean definitions for {@link ServletWebServerFactoryConfiguration}.
 */
@Generated
public class ServletWebServerFactoryConfiguration__BeanDefinitions {
  /**
   * Bean definitions for {@link ServletWebServerFactoryConfiguration.EmbeddedTomcat}.
   */
  @Generated
  public static class EmbeddedTomcat {
    /**
     * Get the bean definition for 'embeddedTomcat'.
     */
    public static BeanDefinition getEmbeddedTomcatBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(ServletWebServerFactoryConfiguration.EmbeddedTomcat.class);
      beanDefinition.setInstanceSupplier(ServletWebServerFactoryConfiguration.EmbeddedTomcat::new);
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'tomcatServletWebServerFactory'.
     */
    private static BeanInstanceSupplier<TomcatServletWebServerFactory> getTomcatServletWebServerFactoryInstanceSupplier(
        ) {
      return BeanInstanceSupplier.<TomcatServletWebServerFactory>forFactoryMethod(ServletWebServerFactoryConfiguration.EmbeddedTomcat.class, "tomcatServletWebServerFactory", ObjectProvider.class, ObjectProvider.class, ObjectProvider.class)
              .withGenerator((registeredBean, args) -> registeredBean.getBeanFactory().getBean(ServletWebServerFactoryConfiguration.EmbeddedTomcat.class).tomcatServletWebServerFactory(args.get(0), args.get(1), args.get(2)));
    }

    /**
     * Get the bean definition for 'tomcatServletWebServerFactory'.
     */
    public static BeanDefinition getTomcatServletWebServerFactoryBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(TomcatServletWebServerFactory.class);
      beanDefinition.setInstanceSupplier(getTomcatServletWebServerFactoryInstanceSupplier());
      return beanDefinition;
    }
  }
}
