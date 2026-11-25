import akka.http.scaladsl.model.HttpMethod
import akka.http.scaladsl.settings.ParserSettings
import play.core.server.{AkkaHttpServer, AkkaHttpServerProvider, ServerProvider}

/** Accept an extension method so HTTP semantics tests reach request instrumentation. */
class SystemTestsAkkaHttpServerProvider extends AkkaHttpServerProvider {
  override def createServer(context: ServerProvider.Context): AkkaHttpServer =
    new AkkaHttpServer(AkkaHttpServer.Context.fromServerProviderContext(context)) {
      override protected def createParserSettings(): ParserSettings =
        super.createParserSettings().withCustomMethods(HttpMethod.custom("PROPFIND"))
    }
}
