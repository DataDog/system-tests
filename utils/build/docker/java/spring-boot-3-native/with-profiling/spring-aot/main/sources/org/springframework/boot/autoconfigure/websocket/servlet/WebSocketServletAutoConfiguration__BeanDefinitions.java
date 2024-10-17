package org.springframework.boot.autoconfigure.websocket.servlet;

import org.springframework.aot.generate.Generated;
import org.springframework.beans.factory.aot.BeanInstanceSupplier;
import org.springframework.beans.factory.config.BeanDefinition;
import org.springframework.beans.factory.support.RootBeanDefinition;

/**
 * Bean definitions for {@link WebSocketServletAutoConfiguration}.
 */
@Generated
public class WebSocketServletAutoConfiguration__BeanDefinitions {
  /**
   * Get the bean definition for 'webSocketServletAutoConfiguration'.
   */
  public static BeanDefinition getWebSocketServletAutoConfigurationBeanDefinition() {
    RootBeanDefinition beanDefinition = new RootBeanDefinition(WebSocketServletAutoConfiguration.class);
    beanDefinition.setInstanceSupplier(WebSocketServletAutoConfiguration::new);
    return beanDefinition;
  }

  /**
   * Bean definitions for {@link WebSocketServletAutoConfiguration.TomcatWebSocketConfiguration}.
   */
  @Generated
  public static class TomcatWebSocketConfiguration {
    /**
     * Get the bean definition for 'tomcatWebSocketConfiguration'.
     */
    public static BeanDefinition getTomcatWebSocketConfigurationBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(WebSocketServletAutoConfiguration.TomcatWebSocketConfiguration.class);
      beanDefinition.setInstanceSupplier(WebSocketServletAutoConfiguration.TomcatWebSocketConfiguration::new);
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'websocketServletWebServerCustomizer'.
     */
    private static BeanInstanceSupplier<TomcatWebSocketServletWebServerCustomizer> getWebsocketServletWebServerCustomizerInstanceSupplier(
        ) {
      return BeanInstanceSupplier.<TomcatWebSocketServletWebServerCustomizer>forFactoryMethod(WebSocketServletAutoConfiguration.TomcatWebSocketConfiguration.class, "websocketServletWebServerCustomizer")
              .withGenerator((registeredBean) -> registeredBean.getBeanFactory().getBean(WebSocketServletAutoConfiguration.TomcatWebSocketConfiguration.class).websocketServletWebServerCustomizer());
    }

    /**
     * Get the bean definition for 'websocketServletWebServerCustomizer'.
     */
    public static BeanDefinition getWebsocketServletWebServerCustomizerBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(TomcatWebSocketServletWebServerCustomizer.class);
      beanDefinition.setInstanceSupplier(getWebsocketServletWebServerCustomizerInstanceSupplier());
      return beanDefinition;
    }
  }
}
