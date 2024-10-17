package org.springframework.boot.autoconfigure.web.servlet;

import java.lang.SuppressWarnings;
import org.springframework.aot.generate.Generated;
import org.springframework.beans.factory.BeanFactory;
import org.springframework.beans.factory.ListableBeanFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.aot.BeanInstanceSupplier;
import org.springframework.beans.factory.config.BeanDefinition;
import org.springframework.beans.factory.support.InstanceSupplier;
import org.springframework.beans.factory.support.RootBeanDefinition;
import org.springframework.boot.autoconfigure.web.WebProperties;
import org.springframework.boot.web.servlet.filter.OrderedFormContentFilter;
import org.springframework.context.ApplicationContext;
import org.springframework.format.support.FormattingConversionService;
import org.springframework.util.PathMatcher;
import org.springframework.validation.Validator;
import org.springframework.web.accept.ContentNegotiationManager;
import org.springframework.web.filter.RequestContextFilter;
import org.springframework.web.method.support.CompositeUriComponentsContributor;
import org.springframework.web.servlet.FlashMapManager;
import org.springframework.web.servlet.HandlerExceptionResolver;
import org.springframework.web.servlet.HandlerMapping;
import org.springframework.web.servlet.LocaleResolver;
import org.springframework.web.servlet.RequestToViewNameTranslator;
import org.springframework.web.servlet.ThemeResolver;
import org.springframework.web.servlet.ViewResolver;
import org.springframework.web.servlet.function.support.HandlerFunctionAdapter;
import org.springframework.web.servlet.function.support.RouterFunctionMapping;
import org.springframework.web.servlet.handler.BeanNameUrlHandlerMapping;
import org.springframework.web.servlet.handler.HandlerMappingIntrospector;
import org.springframework.web.servlet.mvc.HttpRequestHandlerAdapter;
import org.springframework.web.servlet.mvc.SimpleControllerHandlerAdapter;
import org.springframework.web.servlet.mvc.method.annotation.RequestMappingHandlerAdapter;
import org.springframework.web.servlet.mvc.method.annotation.RequestMappingHandlerMapping;
import org.springframework.web.servlet.resource.ResourceUrlProvider;
import org.springframework.web.servlet.view.ContentNegotiatingViewResolver;
import org.springframework.web.servlet.view.InternalResourceViewResolver;
import org.springframework.web.util.UrlPathHelper;
import org.springframework.web.util.pattern.PathPatternParser;

/**
 * Bean definitions for {@link WebMvcAutoConfiguration}.
 */
@Generated
public class WebMvcAutoConfiguration__BeanDefinitions {
  /**
   * Get the bean definition for 'webMvcAutoConfiguration'.
   */
  public static BeanDefinition getWebMvcAutoConfigurationBeanDefinition() {
    RootBeanDefinition beanDefinition = new RootBeanDefinition(WebMvcAutoConfiguration.class);
    beanDefinition.setInstanceSupplier(WebMvcAutoConfiguration::new);
    return beanDefinition;
  }

  /**
   * Get the bean instance supplier for 'formContentFilter'.
   */
  private static BeanInstanceSupplier<OrderedFormContentFilter> getFormContentFilterInstanceSupplier(
      ) {
    return BeanInstanceSupplier.<OrderedFormContentFilter>forFactoryMethod(WebMvcAutoConfiguration.class, "formContentFilter")
            .withGenerator((registeredBean) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.class).formContentFilter());
  }

  /**
   * Get the bean definition for 'formContentFilter'.
   */
  public static BeanDefinition getFormContentFilterBeanDefinition() {
    RootBeanDefinition beanDefinition = new RootBeanDefinition(OrderedFormContentFilter.class);
    beanDefinition.setInstanceSupplier(getFormContentFilterInstanceSupplier());
    return beanDefinition;
  }

  /**
   * Bean definitions for {@link WebMvcAutoConfiguration.WebMvcAutoConfigurationAdapter}.
   */
  @Generated
  public static class WebMvcAutoConfigurationAdapter {
    /**
     * Get the bean instance supplier for 'org.springframework.boot.autoconfigure.web.servlet.WebMvcAutoConfiguration$WebMvcAutoConfigurationAdapter'.
     */
    private static BeanInstanceSupplier<WebMvcAutoConfiguration.WebMvcAutoConfigurationAdapter> getWebMvcAutoConfigurationAdapterInstanceSupplier(
        ) {
      return BeanInstanceSupplier.<WebMvcAutoConfiguration.WebMvcAutoConfigurationAdapter>forConstructor(WebProperties.class, WebMvcProperties.class, ListableBeanFactory.class, ObjectProvider.class, ObjectProvider.class, ObjectProvider.class, ObjectProvider.class)
              .withGenerator((registeredBean, args) -> new WebMvcAutoConfiguration.WebMvcAutoConfigurationAdapter(args.get(0), args.get(1), args.get(2), args.get(3), args.get(4), args.get(5), args.get(6)));
    }

    /**
     * Get the bean definition for 'webMvcAutoConfigurationAdapter'.
     */
    public static BeanDefinition getWebMvcAutoConfigurationAdapterBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(WebMvcAutoConfiguration.WebMvcAutoConfigurationAdapter.class);
      beanDefinition.setInstanceSupplier(getWebMvcAutoConfigurationAdapterInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'defaultViewResolver'.
     */
    private static BeanInstanceSupplier<InternalResourceViewResolver> getDefaultViewResolverInstanceSupplier(
        ) {
      return BeanInstanceSupplier.<InternalResourceViewResolver>forFactoryMethod(WebMvcAutoConfiguration.WebMvcAutoConfigurationAdapter.class, "defaultViewResolver")
              .withGenerator((registeredBean) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.WebMvcAutoConfigurationAdapter.class).defaultViewResolver());
    }

    /**
     * Get the bean definition for 'defaultViewResolver'.
     */
    public static BeanDefinition getDefaultViewResolverBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(InternalResourceViewResolver.class);
      beanDefinition.setInstanceSupplier(getDefaultViewResolverInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'viewResolver'.
     */
    private static BeanInstanceSupplier<ContentNegotiatingViewResolver> getViewResolverInstanceSupplier(
        ) {
      return BeanInstanceSupplier.<ContentNegotiatingViewResolver>forFactoryMethod(WebMvcAutoConfiguration.WebMvcAutoConfigurationAdapter.class, "viewResolver", BeanFactory.class)
              .withGenerator((registeredBean, args) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.WebMvcAutoConfigurationAdapter.class).viewResolver(args.get(0)));
    }

    /**
     * Get the bean definition for 'viewResolver'.
     */
    public static BeanDefinition getViewResolverBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(ContentNegotiatingViewResolver.class);
      beanDefinition.setInstanceSupplier(getViewResolverInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean definition for 'requestContextFilter'.
     */
    public static BeanDefinition getRequestContextFilterBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(WebMvcAutoConfiguration.WebMvcAutoConfigurationAdapter.class);
      beanDefinition.setTargetType(RequestContextFilter.class);
      beanDefinition.setInstanceSupplier(BeanInstanceSupplier.<RequestContextFilter>forFactoryMethod(WebMvcAutoConfiguration.WebMvcAutoConfigurationAdapter.class, "requestContextFilter").withGenerator((registeredBean) -> WebMvcAutoConfiguration.WebMvcAutoConfigurationAdapter.requestContextFilter()));
      return beanDefinition;
    }
  }

  /**
   * Bean definitions for {@link WebMvcAutoConfiguration.EnableWebMvcConfiguration}.
   */
  @Generated
  public static class EnableWebMvcConfiguration {
    /**
     * Get the bean instance supplier for 'org.springframework.boot.autoconfigure.web.servlet.WebMvcAutoConfiguration$EnableWebMvcConfiguration'.
     */
    private static BeanInstanceSupplier<WebMvcAutoConfiguration.EnableWebMvcConfiguration> getEnableWebMvcConfigurationInstanceSupplier(
        ) {
      return BeanInstanceSupplier.<WebMvcAutoConfiguration.EnableWebMvcConfiguration>forConstructor(WebMvcProperties.class, WebProperties.class, ObjectProvider.class, ObjectProvider.class, ListableBeanFactory.class)
              .withGenerator((registeredBean, args) -> new WebMvcAutoConfiguration.EnableWebMvcConfiguration(args.get(0), args.get(1), args.get(2), args.get(3), args.get(4)));
    }

    /**
     * Get the bean definition for 'enableWebMvcConfiguration'.
     */
    public static BeanDefinition getEnableWebMvcConfigurationBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class);
      InstanceSupplier<WebMvcAutoConfiguration.EnableWebMvcConfiguration> instanceSupplier = getEnableWebMvcConfigurationInstanceSupplier();
      instanceSupplier = instanceSupplier.andThen(WebMvcAutoConfiguration_EnableWebMvcConfiguration__Autowiring::apply);
      beanDefinition.setInstanceSupplier(instanceSupplier);
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'welcomePageHandlerMapping'.
     */
    private static BeanInstanceSupplier<WelcomePageHandlerMapping> getWelcomePageHandlerMappingInstanceSupplier(
        ) {
      return BeanInstanceSupplier.<WelcomePageHandlerMapping>forFactoryMethod(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class, "welcomePageHandlerMapping", ApplicationContext.class, FormattingConversionService.class, ResourceUrlProvider.class)
              .withGenerator((registeredBean, args) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class).welcomePageHandlerMapping(args.get(0), args.get(1), args.get(2)));
    }

    /**
     * Get the bean definition for 'welcomePageHandlerMapping'.
     */
    public static BeanDefinition getWelcomePageHandlerMappingBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(WelcomePageHandlerMapping.class);
      beanDefinition.setInstanceSupplier(getWelcomePageHandlerMappingInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'welcomePageNotAcceptableHandlerMapping'.
     */
    private static BeanInstanceSupplier<WelcomePageNotAcceptableHandlerMapping> getWelcomePageNotAcceptableHandlerMappingInstanceSupplier(
        ) {
      return BeanInstanceSupplier.<WelcomePageNotAcceptableHandlerMapping>forFactoryMethod(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class, "welcomePageNotAcceptableHandlerMapping", ApplicationContext.class, FormattingConversionService.class, ResourceUrlProvider.class)
              .withGenerator((registeredBean, args) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class).welcomePageNotAcceptableHandlerMapping(args.get(0), args.get(1), args.get(2)));
    }

    /**
     * Get the bean definition for 'welcomePageNotAcceptableHandlerMapping'.
     */
    public static BeanDefinition getWelcomePageNotAcceptableHandlerMappingBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(WelcomePageNotAcceptableHandlerMapping.class);
      beanDefinition.setInstanceSupplier(getWelcomePageNotAcceptableHandlerMappingInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'localeResolver'.
     */
    private static BeanInstanceSupplier<LocaleResolver> getLocaleResolverInstanceSupplier() {
      return BeanInstanceSupplier.<LocaleResolver>forFactoryMethod(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class, "localeResolver")
              .withGenerator((registeredBean) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class).localeResolver());
    }

    /**
     * Get the bean definition for 'localeResolver'.
     */
    public static BeanDefinition getLocaleResolverBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(LocaleResolver.class);
      beanDefinition.setInstanceSupplier(getLocaleResolverInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'themeResolver'.
     */
    @SuppressWarnings("deprecation")
    private static BeanInstanceSupplier<ThemeResolver> getThemeResolverInstanceSupplier() {
      return BeanInstanceSupplier.<ThemeResolver>forFactoryMethod(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class, "themeResolver")
              .withGenerator((registeredBean) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class).themeResolver());
    }

    /**
     * Get the bean definition for 'themeResolver'.
     */
    @SuppressWarnings("deprecation")
    public static BeanDefinition getThemeResolverBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(ThemeResolver.class);
      beanDefinition.setInstanceSupplier(getThemeResolverInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'flashMapManager'.
     */
    private static BeanInstanceSupplier<FlashMapManager> getFlashMapManagerInstanceSupplier() {
      return BeanInstanceSupplier.<FlashMapManager>forFactoryMethod(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class, "flashMapManager")
              .withGenerator((registeredBean) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class).flashMapManager());
    }

    /**
     * Get the bean definition for 'flashMapManager'.
     */
    public static BeanDefinition getFlashMapManagerBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(FlashMapManager.class);
      beanDefinition.setInstanceSupplier(getFlashMapManagerInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'mvcConversionService'.
     */
    private static BeanInstanceSupplier<FormattingConversionService> getMvcConversionServiceInstanceSupplier(
        ) {
      return BeanInstanceSupplier.<FormattingConversionService>forFactoryMethod(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class, "mvcConversionService")
              .withGenerator((registeredBean) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class).mvcConversionService());
    }

    /**
     * Get the bean definition for 'mvcConversionService'.
     */
    public static BeanDefinition getMvcConversionServiceBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(FormattingConversionService.class);
      beanDefinition.setInstanceSupplier(getMvcConversionServiceInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'mvcValidator'.
     */
    private static BeanInstanceSupplier<Validator> getMvcValidatorInstanceSupplier() {
      return BeanInstanceSupplier.<Validator>forFactoryMethod(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class, "mvcValidator")
              .withGenerator((registeredBean) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class).mvcValidator());
    }

    /**
     * Get the bean definition for 'mvcValidator'.
     */
    public static BeanDefinition getMvcValidatorBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(Validator.class);
      beanDefinition.setInstanceSupplier(getMvcValidatorInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'mvcContentNegotiationManager'.
     */
    private static BeanInstanceSupplier<ContentNegotiationManager> getMvcContentNegotiationManagerInstanceSupplier(
        ) {
      return BeanInstanceSupplier.<ContentNegotiationManager>forFactoryMethod(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class, "mvcContentNegotiationManager")
              .withGenerator((registeredBean) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class).mvcContentNegotiationManager());
    }

    /**
     * Get the bean definition for 'mvcContentNegotiationManager'.
     */
    public static BeanDefinition getMvcContentNegotiationManagerBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(ContentNegotiationManager.class);
      beanDefinition.setInstanceSupplier(getMvcContentNegotiationManagerInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'requestMappingHandlerMapping'.
     */
    private static BeanInstanceSupplier<RequestMappingHandlerMapping> getRequestMappingHandlerMappingInstanceSupplier(
        ) {
      return BeanInstanceSupplier.<RequestMappingHandlerMapping>forFactoryMethod(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class, "requestMappingHandlerMapping", ContentNegotiationManager.class, FormattingConversionService.class, ResourceUrlProvider.class)
              .withGenerator((registeredBean, args) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class).requestMappingHandlerMapping(args.get(0), args.get(1), args.get(2)));
    }

    /**
     * Get the bean definition for 'requestMappingHandlerMapping'.
     */
    public static BeanDefinition getRequestMappingHandlerMappingBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(RequestMappingHandlerMapping.class);
      beanDefinition.setInstanceSupplier(getRequestMappingHandlerMappingInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'mvcPatternParser'.
     */
    private static BeanInstanceSupplier<PathPatternParser> getMvcPatternParserInstanceSupplier() {
      return BeanInstanceSupplier.<PathPatternParser>forFactoryMethod(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class, "mvcPatternParser")
              .withGenerator((registeredBean) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class).mvcPatternParser());
    }

    /**
     * Get the bean definition for 'mvcPatternParser'.
     */
    public static BeanDefinition getMvcPatternParserBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(PathPatternParser.class);
      beanDefinition.setInstanceSupplier(getMvcPatternParserInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'mvcUrlPathHelper'.
     */
    private static BeanInstanceSupplier<UrlPathHelper> getMvcUrlPathHelperInstanceSupplier() {
      return BeanInstanceSupplier.<UrlPathHelper>forFactoryMethod(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class, "mvcUrlPathHelper")
              .withGenerator((registeredBean) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class).mvcUrlPathHelper());
    }

    /**
     * Get the bean definition for 'mvcUrlPathHelper'.
     */
    public static BeanDefinition getMvcUrlPathHelperBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(UrlPathHelper.class);
      beanDefinition.setInstanceSupplier(getMvcUrlPathHelperInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'mvcPathMatcher'.
     */
    private static BeanInstanceSupplier<PathMatcher> getMvcPathMatcherInstanceSupplier() {
      return BeanInstanceSupplier.<PathMatcher>forFactoryMethod(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class, "mvcPathMatcher")
              .withGenerator((registeredBean) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class).mvcPathMatcher());
    }

    /**
     * Get the bean definition for 'mvcPathMatcher'.
     */
    public static BeanDefinition getMvcPathMatcherBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(PathMatcher.class);
      beanDefinition.setInstanceSupplier(getMvcPathMatcherInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'viewControllerHandlerMapping'.
     */
    private static BeanInstanceSupplier<HandlerMapping> getViewControllerHandlerMappingInstanceSupplier(
        ) {
      return BeanInstanceSupplier.<HandlerMapping>forFactoryMethod(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class, "viewControllerHandlerMapping", FormattingConversionService.class, ResourceUrlProvider.class)
              .withGenerator((registeredBean, args) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class).viewControllerHandlerMapping(args.get(0), args.get(1)));
    }

    /**
     * Get the bean definition for 'viewControllerHandlerMapping'.
     */
    public static BeanDefinition getViewControllerHandlerMappingBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(HandlerMapping.class);
      beanDefinition.setInstanceSupplier(getViewControllerHandlerMappingInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'beanNameHandlerMapping'.
     */
    private static BeanInstanceSupplier<BeanNameUrlHandlerMapping> getBeanNameHandlerMappingInstanceSupplier(
        ) {
      return BeanInstanceSupplier.<BeanNameUrlHandlerMapping>forFactoryMethod(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class, "beanNameHandlerMapping", FormattingConversionService.class, ResourceUrlProvider.class)
              .withGenerator((registeredBean, args) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class).beanNameHandlerMapping(args.get(0), args.get(1)));
    }

    /**
     * Get the bean definition for 'beanNameHandlerMapping'.
     */
    public static BeanDefinition getBeanNameHandlerMappingBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(BeanNameUrlHandlerMapping.class);
      beanDefinition.setInstanceSupplier(getBeanNameHandlerMappingInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'routerFunctionMapping'.
     */
    private static BeanInstanceSupplier<RouterFunctionMapping> getRouterFunctionMappingInstanceSupplier(
        ) {
      return BeanInstanceSupplier.<RouterFunctionMapping>forFactoryMethod(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class, "routerFunctionMapping", FormattingConversionService.class, ResourceUrlProvider.class)
              .withGenerator((registeredBean, args) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class).routerFunctionMapping(args.get(0), args.get(1)));
    }

    /**
     * Get the bean definition for 'routerFunctionMapping'.
     */
    public static BeanDefinition getRouterFunctionMappingBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(RouterFunctionMapping.class);
      beanDefinition.setInstanceSupplier(getRouterFunctionMappingInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'resourceHandlerMapping'.
     */
    private static BeanInstanceSupplier<HandlerMapping> getResourceHandlerMappingInstanceSupplier(
        ) {
      return BeanInstanceSupplier.<HandlerMapping>forFactoryMethod(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class, "resourceHandlerMapping", ContentNegotiationManager.class, FormattingConversionService.class, ResourceUrlProvider.class)
              .withGenerator((registeredBean, args) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class).resourceHandlerMapping(args.get(0), args.get(1), args.get(2)));
    }

    /**
     * Get the bean definition for 'resourceHandlerMapping'.
     */
    public static BeanDefinition getResourceHandlerMappingBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(HandlerMapping.class);
      beanDefinition.setInstanceSupplier(getResourceHandlerMappingInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'mvcResourceUrlProvider'.
     */
    private static BeanInstanceSupplier<ResourceUrlProvider> getMvcResourceUrlProviderInstanceSupplier(
        ) {
      return BeanInstanceSupplier.<ResourceUrlProvider>forFactoryMethod(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class, "mvcResourceUrlProvider")
              .withGenerator((registeredBean) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class).mvcResourceUrlProvider());
    }

    /**
     * Get the bean definition for 'mvcResourceUrlProvider'.
     */
    public static BeanDefinition getMvcResourceUrlProviderBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(ResourceUrlProvider.class);
      beanDefinition.setInstanceSupplier(getMvcResourceUrlProviderInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'defaultServletHandlerMapping'.
     */
    private static BeanInstanceSupplier<HandlerMapping> getDefaultServletHandlerMappingInstanceSupplier(
        ) {
      return BeanInstanceSupplier.<HandlerMapping>forFactoryMethod(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class, "defaultServletHandlerMapping")
              .withGenerator((registeredBean) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class).defaultServletHandlerMapping());
    }

    /**
     * Get the bean definition for 'defaultServletHandlerMapping'.
     */
    public static BeanDefinition getDefaultServletHandlerMappingBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(HandlerMapping.class);
      beanDefinition.setInstanceSupplier(getDefaultServletHandlerMappingInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'requestMappingHandlerAdapter'.
     */
    private static BeanInstanceSupplier<RequestMappingHandlerAdapter> getRequestMappingHandlerAdapterInstanceSupplier(
        ) {
      return BeanInstanceSupplier.<RequestMappingHandlerAdapter>forFactoryMethod(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class, "requestMappingHandlerAdapter", ContentNegotiationManager.class, FormattingConversionService.class, Validator.class)
              .withGenerator((registeredBean, args) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class).requestMappingHandlerAdapter(args.get(0), args.get(1), args.get(2)));
    }

    /**
     * Get the bean definition for 'requestMappingHandlerAdapter'.
     */
    public static BeanDefinition getRequestMappingHandlerAdapterBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(RequestMappingHandlerAdapter.class);
      beanDefinition.setInstanceSupplier(getRequestMappingHandlerAdapterInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'handlerFunctionAdapter'.
     */
    private static BeanInstanceSupplier<HandlerFunctionAdapter> getHandlerFunctionAdapterInstanceSupplier(
        ) {
      return BeanInstanceSupplier.<HandlerFunctionAdapter>forFactoryMethod(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class, "handlerFunctionAdapter")
              .withGenerator((registeredBean) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class).handlerFunctionAdapter());
    }

    /**
     * Get the bean definition for 'handlerFunctionAdapter'.
     */
    public static BeanDefinition getHandlerFunctionAdapterBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(HandlerFunctionAdapter.class);
      beanDefinition.setInstanceSupplier(getHandlerFunctionAdapterInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'mvcUriComponentsContributor'.
     */
    private static BeanInstanceSupplier<CompositeUriComponentsContributor> getMvcUriComponentsContributorInstanceSupplier(
        ) {
      return BeanInstanceSupplier.<CompositeUriComponentsContributor>forFactoryMethod(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class, "mvcUriComponentsContributor", FormattingConversionService.class, RequestMappingHandlerAdapter.class)
              .withGenerator((registeredBean, args) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class).mvcUriComponentsContributor(args.get(0), args.get(1)));
    }

    /**
     * Get the bean definition for 'mvcUriComponentsContributor'.
     */
    public static BeanDefinition getMvcUriComponentsContributorBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(CompositeUriComponentsContributor.class);
      beanDefinition.setInstanceSupplier(getMvcUriComponentsContributorInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'httpRequestHandlerAdapter'.
     */
    private static BeanInstanceSupplier<HttpRequestHandlerAdapter> getHttpRequestHandlerAdapterInstanceSupplier(
        ) {
      return BeanInstanceSupplier.<HttpRequestHandlerAdapter>forFactoryMethod(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class, "httpRequestHandlerAdapter")
              .withGenerator((registeredBean) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class).httpRequestHandlerAdapter());
    }

    /**
     * Get the bean definition for 'httpRequestHandlerAdapter'.
     */
    public static BeanDefinition getHttpRequestHandlerAdapterBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(HttpRequestHandlerAdapter.class);
      beanDefinition.setInstanceSupplier(getHttpRequestHandlerAdapterInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'simpleControllerHandlerAdapter'.
     */
    private static BeanInstanceSupplier<SimpleControllerHandlerAdapter> getSimpleControllerHandlerAdapterInstanceSupplier(
        ) {
      return BeanInstanceSupplier.<SimpleControllerHandlerAdapter>forFactoryMethod(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class, "simpleControllerHandlerAdapter")
              .withGenerator((registeredBean) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class).simpleControllerHandlerAdapter());
    }

    /**
     * Get the bean definition for 'simpleControllerHandlerAdapter'.
     */
    public static BeanDefinition getSimpleControllerHandlerAdapterBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(SimpleControllerHandlerAdapter.class);
      beanDefinition.setInstanceSupplier(getSimpleControllerHandlerAdapterInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'handlerExceptionResolver'.
     */
    private static BeanInstanceSupplier<HandlerExceptionResolver> getHandlerExceptionResolverInstanceSupplier(
        ) {
      return BeanInstanceSupplier.<HandlerExceptionResolver>forFactoryMethod(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class, "handlerExceptionResolver", ContentNegotiationManager.class)
              .withGenerator((registeredBean, args) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class).handlerExceptionResolver(args.get(0)));
    }

    /**
     * Get the bean definition for 'handlerExceptionResolver'.
     */
    public static BeanDefinition getHandlerExceptionResolverBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(HandlerExceptionResolver.class);
      beanDefinition.setInstanceSupplier(getHandlerExceptionResolverInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'mvcViewResolver'.
     */
    private static BeanInstanceSupplier<ViewResolver> getMvcViewResolverInstanceSupplier() {
      return BeanInstanceSupplier.<ViewResolver>forFactoryMethod(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class, "mvcViewResolver", ContentNegotiationManager.class)
              .withGenerator((registeredBean, args) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class).mvcViewResolver(args.get(0)));
    }

    /**
     * Get the bean definition for 'mvcViewResolver'.
     */
    public static BeanDefinition getMvcViewResolverBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(ViewResolver.class);
      beanDefinition.setInstanceSupplier(getMvcViewResolverInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'mvcHandlerMappingIntrospector'.
     */
    private static BeanInstanceSupplier<HandlerMappingIntrospector> getMvcHandlerMappingIntrospectorInstanceSupplier(
        ) {
      return BeanInstanceSupplier.<HandlerMappingIntrospector>forFactoryMethod(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class, "mvcHandlerMappingIntrospector")
              .withGenerator((registeredBean) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class).mvcHandlerMappingIntrospector());
    }

    /**
     * Get the bean definition for 'mvcHandlerMappingIntrospector'.
     */
    public static BeanDefinition getMvcHandlerMappingIntrospectorBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(HandlerMappingIntrospector.class);
      beanDefinition.setLazyInit(true);
      beanDefinition.setInstanceSupplier(getMvcHandlerMappingIntrospectorInstanceSupplier());
      return beanDefinition;
    }

    /**
     * Get the bean instance supplier for 'viewNameTranslator'.
     */
    private static BeanInstanceSupplier<RequestToViewNameTranslator> getViewNameTranslatorInstanceSupplier(
        ) {
      return BeanInstanceSupplier.<RequestToViewNameTranslator>forFactoryMethod(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class, "viewNameTranslator")
              .withGenerator((registeredBean) -> registeredBean.getBeanFactory().getBean(WebMvcAutoConfiguration.EnableWebMvcConfiguration.class).viewNameTranslator());
    }

    /**
     * Get the bean definition for 'viewNameTranslator'.
     */
    public static BeanDefinition getViewNameTranslatorBeanDefinition() {
      RootBeanDefinition beanDefinition = new RootBeanDefinition(RequestToViewNameTranslator.class);
      beanDefinition.setInstanceSupplier(getViewNameTranslatorInstanceSupplier());
      return beanDefinition;
    }
  }
}
