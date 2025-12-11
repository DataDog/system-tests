package com.datadoghq.system_tests.springboot;

import com.datadoghq.system_tests.iast.utils.*;
import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import java.security.MessageDigest;
import java.nio.charset.StandardCharsets;
import java.security.NoSuchAlgorithmException;

import javax.mail.MessagingException;
import javax.naming.Context;
import javax.naming.NamingException;
import javax.naming.directory.InitialDirContext;
import javax.servlet.ServletException;
import javax.servlet.ServletRequest;
import javax.servlet.ServletResponse;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import javax.sql.DataSource;
import java.io.IOException;
import java.util.Hashtable;

import org.apache.commons.lang3.StringEscapeUtils;

@RestController
@RequestMapping("/iast")
public class AppSecIast {
    String superSecretAccessKey = "insecure";

    private final SqlExamples sqlExamples;
    private final CmdExamples cmdExamples;
    private final PathExamples pathExamples;
    private final CryptoExamples cryptoExamples;
    private volatile LDAPExamples ldapExamples;
    private final SsrfExamples ssrfExamples;
    private final WeakRandomnessExamples weakRandomnessExamples;
    private final XPathExamples xPathExamples;
    private final XSSExamples xssExamples;
    private final HardcodedSecretExamples hardcodedSecretExamples;
    private final ReflectionExamples reflectionExamples;
    private final DeserializationExamples deserializationExamples;
    private final EmailExamples emailExamples;


    public AppSecIast(final DataSource dataSource) {
        this.sqlExamples = new SqlExamples(dataSource);
        this.cmdExamples = new CmdExamples();
        this.pathExamples = new PathExamples();
        this.cryptoExamples = new CryptoExamples();
        this.ssrfExamples = new SsrfExamples();
        this.weakRandomnessExamples = new WeakRandomnessExamples();
        this.xPathExamples = new XPathExamples();
        this.xssExamples = new XSSExamples();
        this.hardcodedSecretExamples = new HardcodedSecretExamples();
        this.reflectionExamples = new ReflectionExamples();
        this.deserializationExamples = new DeserializationExamples();
        this.emailExamples = new EmailExamples();
    }

    @RequestMapping("/hardcoded_secrets/test_insecure")
    String hardcodedSecrets() {
        return hardcodedSecretExamples.SECRET;
    }

    @RequestMapping("/insecure_hashing/deduplicate")
    String removeDuplicates() {
        return cryptoExamples.removeDuplicates(superSecretAccessKey);
    }

    @RequestMapping("/insecure_hashing/multiple_hash")
    String multipleInsecureHash() {
        return cryptoExamples.multipleInsecureHash(superSecretAccessKey);
    }

    @RequestMapping("/insecure_hashing/test_secure_algorithm")
    String secureHashing() {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return cryptoExamples.secureHashing(superSecretAccessKey);
    }

    @RequestMapping("/insecure_hashing/test_md5_algorithm")
    String insecureMd5Hashing() {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return cryptoExamples.insecureMd5Hashing(superSecretAccessKey);
    }

    @RequestMapping("/insecure_cipher/test_secure_algorithm")
    String secureCipher() {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return cryptoExamples.secureCipher(superSecretAccessKey);
    }

    @RequestMapping("/insecure_cipher/test_insecure_algorithm")
    String insecureCipher() {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return cryptoExamples.insecureCipher(superSecretAccessKey);
    }

    @PostMapping("/unvalidated_redirect/test_secure_header")
    public String secureHeader(HttpServletResponse response) {
        response.setHeader("location", "http://dummy.location.com");
        return "redirect";
    }

    @PostMapping("/unvalidated_redirect/test_insecure_header")
    public String insecureHeader(final ServletRequest request, final HttpServletResponse response) {
        final String location = request.getParameter("location");
        response.setHeader("location", location);
        return "redirect";
    }

    @PostMapping("/unvalidated_redirect/test_secure_redirect")
    public String secureRedirect(HttpServletResponse response) throws IOException {
        response.sendRedirect("http://dummy.location.com");
        return "redirect";
    }

    @PostMapping("/unvalidated_redirect/test_insecure_redirect")
    public String insecureRedirect(final ServletRequest request, final HttpServletResponse response) throws IOException {
        final String location = request.getParameter("location");
        response.sendRedirect(location);
        return "redirect";
    }

    @PostMapping("/unvalidated_redirect/test_secure_forward")
    public String secureForward(HttpServletRequest request, final HttpServletResponse response) throws ServletException, IOException {
        request.getRequestDispatcher("http://dummy.location.com").forward(request, response);
        return "redirect";
    }

    @PostMapping("/unvalidated_redirect/test_insecure_forward")
    public String insecureForward(final ServletRequest request, final HttpServletResponse response) throws IOException, ServletException {
        final String location = request.getParameter("location");
        request.getRequestDispatcher(location).forward(request, response);
        return "redirect";
    }

    @PostMapping("/sqli/test_insecure")
    Object insecureSql(final ServletRequest request) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        final String username = request.getParameter("username");
        final String password = request.getParameter("password");
        return sqlExamples.insecureSql(username, password);
    }

    @PostMapping("/sqli/test_secure")
    Object secureSql(final ServletRequest request) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        final String username = request.getParameter("username");
        final String password = request.getParameter("password");
        return sqlExamples.secureSql(username, password);
    }

    @PostMapping("/cmdi/test_insecure")
    String insecureCmd(final ServletRequest request) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        final String cmd = request.getParameter("cmd");
        return cmdExamples.insecureCmd(cmd);
    }

    @PostMapping("/ldapi/test_insecure")
    String insecureLDAP(final ServletRequest request) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        final String username = request.getParameter("username");
        final String password = request.getParameter("password");
        return getOrCreateLdapExamples().injection(username, password);
    }

    @PostMapping("/ldapi/test_secure")
    String secureLDAP() {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return getOrCreateLdapExamples().secure();
    }


    @PostMapping("/path_traversal/test_insecure")
    String insecurePathTraversal(final ServletRequest request) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        final String path = request.getParameter("path");
        return pathExamples.insecurePathTraversal(path);
    }

    @PostMapping("/ssrf/test_insecure")
    String insecureSsrf(final ServletRequest request) {
        final String url = request.getParameter("url");
        return ssrfExamples.insecureUrl(url);
    }

    @GetMapping("/weak_randomness/test_insecure")
    String insecureRandom() {
        return weakRandomnessExamples.weakRandom();
    }

    @GetMapping("/weak_randomness/test_secure")
    String secureRandom() {
        return weakRandomnessExamples.secureRandom();
    }

    @GetMapping("/insecure-cookie/test_empty_cookie")
    String insecureCookieEmptyCookie(final HttpServletResponse response) {
        response.addHeader("Set-Cookie", "");
        return "ok";
    }

    @GetMapping("/insecure-cookie/test_insecure")
    String insecureCookie(final HttpServletResponse response) {
        response.addHeader("Set-Cookie", "user-id=7;HttpOnly;SameSite=Strict");
        return "ok";
    }

    @GetMapping("/insecure-cookie/test_secure")
    String secureCookie(final HttpServletResponse response) {
        response.addHeader("Set-Cookie", "user-id=7;Secure;HttpOnly;SameSite=Strict");
        return "ok";
    }

    @GetMapping("/no-samesite-cookie/test_insecure")
    String noSameSiteCookieInsecure(final HttpServletResponse response) {
        response.addHeader("Set-Cookie", "user-id=7;HttpOnly;Secure");
        return "ok";
    }

    @GetMapping("/no-samesite-cookie/test_empty_cookie")
    String noSameSiteCookieEmptyCookie(final HttpServletResponse response) {
        response.addHeader("Set-Cookie", "");
        return "ok";
    }

    @GetMapping("/no-samesite-cookie/test_secure")
    String noSameSiteCookieSecure(final HttpServletResponse response) {
        response.addHeader("Set-Cookie", "user-id=7;Secure;HttpOnly;SameSite=Strict");
        return "ok";
    }

    @GetMapping("/no-httponly-cookie/test_empty_cookie")
    String noHttpOnlyCookieEmptyCookie(final HttpServletResponse response) {
        response.addHeader("Set-Cookie", "");
        return "ok";
    }
    @GetMapping("/no-httponly-cookie/test_insecure")
    String noHttpOnlyCookieInsecure(final HttpServletResponse response) {
        response.addHeader("Set-Cookie", "user-id=7;Secure;SameSite=Strict");
        return "ok";
    }

    @GetMapping("/no-httponly-cookie/test_secure")
    String noHttpOnlyCookieSecure(final HttpServletResponse response) {
        response.addHeader("Set-Cookie", "user-id=7;Secure;HttpOnly;SameSite=Strict");
        return "ok";
    }

    @PostMapping("/xpathi/test_insecure")
    String insecureXPath(final ServletRequest request) {
        final String expression = request.getParameter("expression");
        xPathExamples.insecureXPath(expression);
        return "XPath insecure";
    }

    @PostMapping("/xpathi/test_secure")
    String secureXPath(final ServletRequest request) {
        xPathExamples.secureXPath();
        return "XPath secure";
    }

    @GetMapping("/trust-boundary-violation/test_insecure")
    public String trustBoundaryViolationInSecureSpringBoot(final HttpServletRequest request) {
      String paramValue = request.getParameter("username");
      request.getSession().putValue("name", paramValue);
      return "Trust Boundary violation page";
    }

    @GetMapping("/trust-boundary-violation/test_secure")
    public String trustBoundaryViolationSecureSpringBoot(final HttpServletRequest request) {
      request.getSession().putValue("name", "value");
      return "Trust Boundary violation page";
    }

    @GetMapping(value="/xcontent-missing-header/test_insecure", produces = "text/html")
    public String xcontentMissingHeaderInsecure(final HttpServletResponse response) {
        response.addHeader("X-Content-Type-Options", "dosniffplease");
        return "ok";
    }

    @GetMapping(value="/xcontent-missing-header/test_secure", produces = "text/html")
    public String xcontentMissingHeaderSecure(final HttpServletResponse response) {
        response.addHeader("X-Content-Type-Options", "nosniff");
        return "ok";
    }

    @PostMapping("/xss/test_insecure")
    void insecureXSS(final ServletRequest request, final ServletResponse response) throws IOException {
        xssExamples.insecureXSS(response.getWriter(), request.getParameter("param"));
    }

    @PostMapping("/xss/test_secure")
    void secureXSS(final ServletResponse response) throws IOException {
        xssExamples.secureXSS(response.getWriter());
    }

    @GetMapping(value = "/hstsmissing/test_insecure", produces = "text/html")
    public String hstsHeaderMissingInsecure(HttpServletResponse response) {
        response.setStatus(HttpStatus.OK.value());
        return "ok";
    }

    @GetMapping(value = "/hstsmissing/test_secure", produces = "text/html")
    public String hstsHeaderMissingSecure(HttpServletResponse response) {
        response.setHeader("Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload");
        response.setStatus(HttpStatus.OK.value());
        return "ok";
    }

    @PostMapping("/header_injection/test_insecure")
    public String headerInjectionInsecure(final HttpServletRequest request, HttpServletResponse response) {
      String paramValue = request.getParameter("test");
      response.addHeader("X-Test-Header", paramValue);
      return "Ok";
    }

    @PostMapping("/header_injection/test_secure")
    public String headerInjectionSecure(final HttpServletRequest request, HttpServletResponse response) {
      String paramValue = request.getParameter("test");
        response.addHeader("Sec-WebSocket-Location", paramValue);
      return "Ok";
    }

    @GetMapping(value = "/insecure-auth-protocol/test")
    public String insecureAuthProtocol(HttpServletResponse response) {
        response.setStatus(HttpStatus.OK.value());
        return "ok";
    }

    @PostMapping(value = "/reflection_injection/test_secure")
    public String secureReflection() {
        return reflectionExamples.secureClassForName();
    }

    @PostMapping(value = "/reflection_injection/test_insecure")
    public String insecureReflection(HttpServletRequest request) {
        final String className = request.getParameter("param");
        return reflectionExamples.insecureClassForName(className);
    }

    @GetMapping("/untrusted_deserialization/test_insecure")
    public String insecureUntrustedDeserialization(final HttpServletRequest request) throws IOException{
        deserializationExamples.insecureDeserialization(request.getInputStream());
        return "ok";
    }

    @GetMapping("/untrusted_deserialization/test_secure")
    public String secureUntrustedDeserialization(final HttpServletRequest request) throws IOException {
        deserializationExamples.secureDeserialization(request.getInputStream());
        return "ok";
    }

    @PostMapping("/sc/s/configured")
    void scSanitizeConfigured(final ServletRequest request,  final ServletResponse response) throws IOException {
        String sanitized = SecurityControlUtil.sanitize(request.getParameter("param"));
        cmdExamples.insecureCmd(sanitized);
    }

    @PostMapping("/sc/s/not-configured")
    Object scSanitizeSqli(final ServletRequest request,  final ServletResponse response) throws IOException {
        String sanitized = SecurityControlUtil.sanitize(request.getParameter("param"));
        return sqlExamples.insecureSql(sanitized, "password");
    }

    @PostMapping("/sc/s/all")
    Object scSanitizeForAllVulns(final ServletRequest request,  final ServletResponse response) throws IOException {
        String sanitized = SecurityControlUtil.sanitizeForAllVulns(request.getParameter("param"));
        return sqlExamples.insecureSql(sanitized, "password");
    }

    @PostMapping("/sc/iv/configured")
    void scValidateXSS(final ServletRequest request,  final ServletResponse response) throws IOException {
        String param = request.getParameter("param");
        if (SecurityControlUtil.validate(param)) {
            cmdExamples.insecureCmd(param);
        }
    }

    @PostMapping("/sc/iv/not-configured")
    void scValidateSqli(final ServletRequest request,  final ServletResponse response) throws IOException {
        String param = request.getParameter("param");
        if(SecurityControlUtil.validate(param)) {
            sqlExamples.insecureSql(param, "password");
        }
    }

    @PostMapping("/sc/iv/all")
    void scValidateForAllVulns(final ServletRequest request,  final ServletResponse response) throws IOException {
        String param = request.getParameter("param");
        if(SecurityControlUtil.validateForAllVulns(param)) {
            sqlExamples.insecureSql(param, "password");
        }
    }

    @PostMapping("/sc/iv/overloaded/secure")
    void scIVOverloadedSecure(final ServletRequest request,  final ServletResponse response) throws IOException {
        String user = request.getParameter("user");
        String pass = request.getParameter("password");
        if(SecurityControlUtil.overloadedValidation(null, user, pass)) {
            sqlExamples.insecureSql(user, pass);
        }
    }

    @PostMapping("/sc/iv/overloaded/insecure")
    void scIVOverloadedInsecure(final ServletRequest request,  final ServletResponse response) throws IOException {
        String user = request.getParameter("user");
        String pass = request.getParameter("password");
        if(SecurityControlUtil.overloadedValidation(user, pass)) {
            sqlExamples.insecureSql(user, pass);
        }
    }

    @PostMapping("/sc/s/overloaded/secure")
    void scSOverloadedSecure(final ServletRequest request,  final ServletResponse response) throws IOException {
        String sanitized = SecurityControlUtil.overloadedSanitize(request.getParameter("param"));
        cmdExamples.insecureCmd(sanitized);
    }

    @PostMapping("/sc/s/overloaded/insecure")
    void scSOverloadedInsecure(final ServletRequest request,  final ServletResponse response) throws IOException {
        String sanitized = SecurityControlUtil.overloadedSanitize(request.getParameter("param"), null);
        cmdExamples.insecureCmd(sanitized);
    }

    @PostMapping("/email_html_injection/test_insecure")
    void emailHtmlInjectionInsecure(final HttpServletRequest request) throws MessagingException {
        String email = request.getParameter("username");
        emailExamples.mail(email);
    }

    @PostMapping("/email_html_injection/test_secure")
    void emailHtmlInjectionSecure(final HttpServletRequest request) throws MessagingException {
        String email = request.getParameter("username");
        emailExamples.mail(StringEscapeUtils.escapeHtml4(email));
    }

    @GetMapping(path = {
            "/sampling-by-route-method-count/{i}",
            "/sampling-by-route-method-count/{i}/"  // optional trailing slash
    })
    void getSampling(
            @PathVariable("i") int i,
            @RequestParam(name = "param", required = false) String paramValue) throws NoSuchAlgorithmException {
        MessageDigest.getInstance("SHA1").digest("hash1".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash2".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash3".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash4".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash5".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash6".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash7".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash8".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash9".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash10".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash11".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash12".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash13".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash14".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash15".getBytes(StandardCharsets.UTF_8));
    }

    @GetMapping(path = {
            "/sampling-by-route-method-count-2/{i}",
            "/sampling-by-route-method-count-2/{i}/"  // optional trailing slash
    })
    void getSampling2(
            @PathVariable("i") int i,
            @RequestParam(name = "param", required = false) String paramValue) throws NoSuchAlgorithmException {
        MessageDigest.getInstance("SHA1").digest("hash1".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash2".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash3".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash4".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash5".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash6".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash7".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash8".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash9".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash10".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash11".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash12".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash13".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash14".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash15".getBytes(StandardCharsets.UTF_8));
    }

    @PostMapping(path = {
            "/sampling-by-route-method-count/{i}",
            "/sampling-by-route-method-count/{i}/"  // optional trailing slash
    })
    void postSampling(
            @PathVariable("i") int i,
            @RequestParam(name = "param", required = false) String paramValue)
            throws NoSuchAlgorithmException  {
        MessageDigest.getInstance("SHA1").digest("hash1".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash2".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash3".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash4".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash5".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash6".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash7".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash8".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash9".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash10".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash11".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash12".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash13".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash14".getBytes(StandardCharsets.UTF_8));
        MessageDigest.getInstance("SHA1").digest("hash15".getBytes(StandardCharsets.UTF_8));
    }

    /**
     * TODO: Ldap is failing to startup in native image this method ensures it's started lazily
     *
     * Native reflection configuration for com.sun.jndi.ldap.LdapCtxFactory is missing.
     */
    private LDAPExamples getOrCreateLdapExamples() {
        if (ldapExamples == null) {
            try {
                Hashtable<String, String> env = new Hashtable<>(3);
                env.put(Context.INITIAL_CONTEXT_FACTORY, "com.sun.jndi.ldap.LdapCtxFactory");
                env.put(Context.PROVIDER_URL, "ldap://localhost:8389/dc=example");
                env.put(Context.SECURITY_AUTHENTICATION, "none");
                this.ldapExamples = new LDAPExamples(new InitialDirContext(env));
            } catch (NamingException e) {
                throw new RuntimeException(e);
            }
        }
        return ldapExamples;
    }
}
