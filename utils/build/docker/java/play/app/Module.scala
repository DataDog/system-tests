import com.google.inject.AbstractModule
import resources.Resources

class Module extends AbstractModule {
  override def configure() = {
    bind(classOf[Resources]).asEagerSingleton()
  }
}
