package com.datadoghq.system_tests.springboot;

import com.datadoghq.system_tests.springboot.iast.utils.CmdExamples;
import com.datadoghq.system_tests.springboot.iast.utils.CryptoExamples;
import com.datadoghq.system_tests.springboot.iast.utils.LDAPExamples;
import com.datadoghq.system_tests.springboot.iast.utils.PathExamples;
import com.datadoghq.system_tests.springboot.iast.utils.SqlExamples;
import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.crypto.BadPaddingException;
import javax.crypto.IllegalBlockSizeException;
import javax.crypto.NoSuchPaddingException;
import javax.naming.NamingException;
import javax.servlet.ServletRequest;
import java.security.InvalidKeyException;
import java.security.NoSuchAlgorithmException;
import java.sql.SQLException;

@RestController
@RequestMapping("/iast")
public class AppSecIast {
    String superSecretAccessKey = "insecure";

    private final CryptoExamples cryptoExamples;
    private final SqlExamples sqlExamples;
    private final CmdExamples cmdExamples;
    private final PathExamples pathExamples;
    private final LDAPExamples ldapExamples;

    public AppSecIast(final CryptoExamples cryptoExamples,
                      final SqlExamples sqlExamples,
                      final CmdExamples cmdExamples,
                      final PathExamples pathExamples,
                      final LDAPExamples ldapExamples) {
        this.cryptoExamples = cryptoExamples;
        this.sqlExamples = sqlExamples;
        this.cmdExamples = cmdExamples;
        this.pathExamples = pathExamples;
        this.ldapExamples = ldapExamples;
    }

    @GetMapping("/")
    String index() {
        return "Welcome to the IAST testing app";
    }

    @RequestMapping("/insecure_hashing/deduplicate")
    String removeDuplicates() throws NoSuchAlgorithmException {
        return cryptoExamples.removeDuplicates(superSecretAccessKey);
    }

    @RequestMapping("/insecure_hashing/multiple_hash")
    String multipleInsecureHash() throws NoSuchAlgorithmException {
        return cryptoExamples.multipleInsecureHash(superSecretAccessKey);
    }

    @RequestMapping("/insecure_hashing/test_secure_algorithm")
    String secureHashing() throws NoSuchAlgorithmException {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return cryptoExamples.secureHashing(superSecretAccessKey);
    }

    @RequestMapping("/insecure_hashing/test_md5_algorithm")
    String insecureMd5Hashing() throws NoSuchAlgorithmException {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return cryptoExamples.insecureMd5Hashing(superSecretAccessKey);
    }

    @RequestMapping("/insecure_cipher/test_secure_algorithm")
    String secureCipher() throws NoSuchAlgorithmException, NoSuchPaddingException,
            IllegalBlockSizeException, BadPaddingException, InvalidKeyException {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return cryptoExamples.secureCipher(superSecretAccessKey);
    }

    @RequestMapping("/insecure_cipher/test_insecure_algorithm")
    String insecureCipher() throws NoSuchAlgorithmException, NoSuchPaddingException,
            IllegalBlockSizeException, BadPaddingException, InvalidKeyException {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return cryptoExamples.insecureCipher(superSecretAccessKey);
    }

    @PostMapping("/sqli/test_insecure")
    Object insecureSql(final ServletRequest request) throws SQLException {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        final String username = request.getParameter("username");
        final String password = request.getParameter("password");
        return sqlExamples.insecureSql(username, password);
    }

    @PostMapping("/sqli/test_secure")
    Object secureSql(final ServletRequest request) throws SQLException {
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
    String insecureLDAP(final ServletRequest request) throws NamingException {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        final String username = request.getParameter("username");
        final String password = request.getParameter("password");
        return ldapExamples.injection(username, password);
    }

    @PostMapping("/ldapi/test_secure")
    String secureLDAP(final ServletRequest request) throws NamingException {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return ldapExamples.secure();
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
}
