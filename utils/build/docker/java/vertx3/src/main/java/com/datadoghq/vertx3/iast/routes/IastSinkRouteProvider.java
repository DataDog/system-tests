package com.datadoghq.vertx3.iast.routes;

import com.datadoghq.system_tests.iast.utils.*;
import io.vertx.core.http.HttpServerRequest;
import io.vertx.core.json.Json;
import io.vertx.ext.web.Router;
import io.vertx.ext.web.handler.BodyHandler;

import javax.naming.directory.InitialDirContext;
import javax.sql.DataSource;
import java.util.function.Consumer;

public class IastSinkRouteProvider implements Consumer<Router> {

    private final DataSource dataSource;
    private final InitialDirContext ldapContext;

    public IastSinkRouteProvider(final DataSource dataSource, final InitialDirContext ldapContext) {
        this.dataSource = dataSource;
        this.ldapContext = ldapContext;
    }

    @Override
    public void accept(final Router router) {
        final String superSecretAccessKey = "insecure";
        final CmdExamples cmd = new CmdExamples();
        final CryptoExamples crypto = new CryptoExamples();
        final LDAPExamples ldap = new LDAPExamples(ldapContext);
        final PathExamples path = new PathExamples();
        final SqlExamples sql = new SqlExamples(dataSource);
        final SsrfExamples ssrf = new SsrfExamples();

        router.route("/iast/*").handler(BodyHandler.create());

        router.get("/iast/insecure_hashing/deduplicate").handler(ctx ->
                ctx.response().end(crypto.removeDuplicates(superSecretAccessKey))
        );
        router.get("/iast/insecure_hashing/multiple_hash").handler(ctx ->
                ctx.response().end(crypto.multipleInsecureHash(superSecretAccessKey))
        );
        router.get("/iast/insecure_hashing/test_secure_algorithm").handler(ctx ->
                ctx.response().end(crypto.secureHashing(superSecretAccessKey))
        );
        router.get("/iast/insecure_hashing/test_md5_algorithm").handler(ctx ->
                ctx.response().end(crypto.insecureMd5Hashing(superSecretAccessKey))
        );
        router.get("/iast/insecure_cipher/test_secure_algorithm").handler(ctx ->
                ctx.response().end(crypto.secureCipher(superSecretAccessKey))
        );
        router.get("/iast/insecure_cipher/test_insecure_algorithm").handler(ctx ->
                ctx.response().end(crypto.insecureCipher(superSecretAccessKey))
        );
        router.post("/iast/sqli/test_insecure").handler(ctx -> {
            final HttpServerRequest request = ctx.request();
            final String username = request.getParam("username");
            final String password = request.getParam("password");
            ctx.response().end(Json.encodeToBuffer(sql.insecureSql(username, password)));
        });
        router.post("/iast/sqli/test_secure").handler(ctx -> {
            final HttpServerRequest request = ctx.request();
            final String username = request.getParam("username");
            final String password = request.getParam("password");
            ctx.response().end(Json.encodeToBuffer(sql.secureSql(username, password)));
        });
        router.post("/iast/ldapi/test_insecure").handler(ctx -> {
            final HttpServerRequest request = ctx.request();
            final String username = request.getParam("username");
            final String password = request.getParam("password");
            ctx.response().end(ldap.injection(username, password));
        });
        router.post("/iast/ldapi/test_secure").handler(ctx -> ctx.response().end(ldap.secure()));
        router.post("/iast/cmdi/test_insecure").handler(ctx -> {
            final HttpServerRequest request = ctx.request();
            final String cmdParam = request.getParam("cmd");
            ctx.response().end(cmd.insecureCmd(cmdParam));
        });
        router.post("/iast/path_traversal/test_insecure").handler(ctx -> {
            final HttpServerRequest request = ctx.request();
            final String pathParam = request.getParam("path");
            ctx.response().end(path.insecurePathTraversal(pathParam));
        });
        router.post("/iast/ssrf/test_insecure").handler(ctx ->
                ctx.response().end(ssrf.insecureUrl(ctx.request().getParam("url")))
        );
    }
}
