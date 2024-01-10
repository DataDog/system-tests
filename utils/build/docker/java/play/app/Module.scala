import com.google.inject.AbstractModule
import play.inject.Module.bindClass
import play.libs.ws.WSClient

class Module extends AbstractModule {
  override def configure() = {
//    bind(classOf[WSClient]).toInstance()
  }

}
