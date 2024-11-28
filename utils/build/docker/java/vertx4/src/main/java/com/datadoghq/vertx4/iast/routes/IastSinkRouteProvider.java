package com.datadoghq.vertx4.iast.routes;

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
        final WeakRandomnessExamples weakRandomness = new WeakRandomnessExamples();
        final XPathExamples xpath = new XPathExamples();
        final ReflectionExamples reflection = new ReflectionExamples();

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
        router.get("/iast/weak_randomness/test_insecure").handler(ctx ->
                ctx.response().end(weakRandomness.weakRandom())
        );
        router.get("/iast/weak_randomness/test_secure").handler(ctx ->
                ctx.response().end(weakRandomness.secureRandom())
        );
        router.post("/iast/unvalidated_redirect/test_insecure_forward").handler(ctx ->{
                    final HttpServerRequest request = ctx.request();
                    final String location = request.getParam("location");
                    ctx.reroute(location);
                }
        );
        router.post("/iast/unvalidated_redirect/test_secure_forward").handler(ctx ->
                ctx.reroute("http://dummy.location.com")
        );
        router.post("/iast/unvalidated_redirect/test_insecure_header").handler(ctx ->
                {
                    final HttpServerRequest request = ctx.request();
                    final String location = request.getParam("location");
                    ctx.response().putHeader("Location", location).end();
                }
        );
        router.post("/iast/unvalidated_redirect/test_secure_header").handler(ctx ->
                ctx.response().putHeader("Location", "http://dummy.location.com").end()
        );
        router.post("/iast/unvalidated_redirect/test_insecure_redirect").handler(ctx ->
                {
                    final HttpServerRequest request = ctx.request();
                    final String location = request.getParam("location");
                    ctx.redirect(location);
                }
        );
        router.post("/iast/unvalidated_redirect/test_secure_redirect").handler(ctx ->
                ctx.redirect("http://dummy.location.com")
        );
        router.post("/iast/xpathi/test_insecure").handler(ctx -> {
            final HttpServerRequest request = ctx.request();
            final String expression = request.getParam("expression");
            xpath.insecureXPath(expression);
            ctx.response().end("Insecure");
        });
        router.post("/iast/xpathi/test_secure").handler(ctx -> {
            xpath.secureXPath();
            ctx.response().end("Secure");
        });
        router.get("/iast/insecure-cookie/test_empty_cookie").handler(ctx ->
                ctx.response().putHeader("Set-Cookie", "").end()
        );
        router.get("/iast/insecure-cookie/test_insecure").handler(ctx ->
                ctx.response().putHeader("Set-Cookie", "user-id=7;HttpOnly;SameSite=Strict").end()
        );
        router.get("/iast/insecure-cookie/test_secure").handler(ctx ->
                ctx.response().putHeader("Set-Cookie", "user-id=7;Secure;HttpOnly;SameSite=Strict").end()
        );
        router.get("/iast/no-samesite-cookie/test_insecure").handler(ctx ->
                ctx.response().putHeader("Set-Cookie", "user-id=7;Secure;HttpOnly").end()
        );
        router.get("/iast/no-samesite-cookie/test_empty_cookie").handler(ctx ->
                ctx.response().putHeader("Set-Cookie", "").end()
        );
        router.get("/iast/no-samesite-cookie/test_secure").handler(ctx ->
                ctx.response().putHeader("Set-Cookie", "user-id=7;Secure;HttpOnly;SameSite=Strict").end()
        );
        router.get("/iast/no-httponly-cookie/test_empty_cookie").handler(ctx ->
                ctx.response().putHeader("Set-Cookie", "").end()
        );
        router.get("/iast/no-httponly-cookie/test_insecure").handler(ctx ->
                ctx.response().putHeader("Set-Cookie", "user-id=7;Secure;SameSite=Strict").end()
        );
        router.get("/iast/no-httponly-cookie/test_secure").handler(ctx ->
                ctx.response().putHeader("Set-Cookie", "user-id=7;Secure;HttpOnly;SameSite=Strict").end()
        );
        router.get("/iast/insecure-auth-protocol/test").handler(ctx ->
                ctx.response().end("ok")
        );
        router.post("/iast/reflection_injection/test_secure").handler(ctx -> {
            ctx.response().end(reflection.secureClassForName());
        });
        router.post("/iast/reflection_injection/test_insecure").handler(ctx -> {
            final HttpServerRequest request = ctx.request();
            final String param = request.getParam("param");
            ctx.response().end(reflection.insecureClassForName(param));
        });
        router.post("/iast/sc/s/configured").handler(ctx -> {
            final HttpServerRequest request = ctx.request();
            String sanitized = SecurityControlUtil.sanitize(request.getParam("param"));
            cmd.insecureCmd(sanitized);
            ctx.response().end();
        });

        router.post("/iast/sc/s/not-configured").handler(ctx -> {
            final HttpServerRequest request = ctx.request();
            String sanitized = SecurityControlUtil.sanitize(request.getParam("param"));
            ctx.response().end(Json.encodeToBuffer(sql.insecureSql(sanitized, "password")));
        });

        router.post("/iast/sc/s/all").handler(ctx -> {
            final HttpServerRequest request = ctx.request();
            String sanitized = SecurityControlUtil.sanitizeForAllVulns(request.getParam("param"));
            ctx.response().end(Json.encodeToBuffer(sql.insecureSql(sanitized, "password")));
        });

        router.post("/iast/sc/iv/configured").handler(ctx -> {
            final HttpServerRequest request = ctx.request();
            String param = request.getParam("param");
            if (SecurityControlUtil.validate(param)) {
                cmd.insecureCmd(param);
            }
            ctx.response().end();
        });

        router.post("/iast/sc/iv/not-configured").handler(ctx -> {
            final HttpServerRequest request = ctx.request();
            String param = request.getParam("param");
            if (SecurityControlUtil.validate(param)) {
                sql.insecureSql(param, "password");
            }
            ctx.response().end();
        });

        router.post("/iast/sc/iv/all").handler(ctx -> {
            final HttpServerRequest request = ctx.request();
            String param = request.getParam("param");
            if (SecurityControlUtil.validateForAllVulns(param)) {
                sql.insecureSql(param, "password");
            }
            ctx.response().end();
        });

        router.post("/iast/sc/iv/overloaded/secure").handler(ctx -> {
            final HttpServerRequest request = ctx.request();
            String user = request.getParam("user");
            String pass = request.getParam("password");
            if (SecurityControlUtil.overloadedValidation(null, user, pass)) {
                sql.insecureSql(user, pass);
            }
            ctx.response().end();
        });

        router.post("/iast/sc/iv/overloaded/insecure").handler(ctx -> {
            final HttpServerRequest request = ctx.request();
            String user = request.getParam("user");
            String pass = request.getParam("password");
            if (SecurityControlUtil.overloadedValidation(user, pass)) {
                sql.insecureSql(user, pass);
            }
            ctx.response().end();
        });

        router.post("/iast/sc/s/overloaded/secure").handler(ctx -> {
            final HttpServerRequest request = ctx.request();
            String sanitized = SecurityControlUtil.overloadedSanitize(request.getParam("param"));
            cmd.insecureCmd(sanitized);
            ctx.response().end();
        });

        router.post("/iast/sc/s/overloaded/insecure").handler(ctx -> {
            final HttpServerRequest request = ctx.request();
            String sanitized = SecurityControlUtil.overloadedSanitize(request.getParam("param"), null);
            cmd.insecureCmd(sanitized);
            ctx.response().end();
        });
    }
}
