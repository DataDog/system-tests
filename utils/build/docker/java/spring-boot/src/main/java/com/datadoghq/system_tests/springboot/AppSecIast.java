package com.datadoghq.system_tests.springboot;

import com.datadoghq.system_tests.springboot.iast.utils.CryptoExamples;
import com.datadoghq.system_tests.springboot.iast.utils.SqlExamples;
import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.servlet.ServletRequest;
import javax.crypto.BadPaddingException;
import javax.crypto.IllegalBlockSizeException;
import javax.crypto.NoSuchPaddingException;
import java.security.InvalidKeyException;
import java.security.NoSuchAlgorithmException;
import java.sql.SQLException;

@RestController
@RequestMapping("/iast")
public class AppSecIast {
    String superSecretAccessKey = "insecure";

    private final SqlExamples sqlExamples;

    public AppSecIast(final SqlExamples sqlExamples) {
        this.sqlExamples = sqlExamples;
    }

    @RequestMapping("/insecure_hashing/deduplicate")
    String removeDuplicates() throws NoSuchAlgorithmException {
        return CryptoExamples.getSingleton().removeDuplicates(superSecretAccessKey);
    }

    @RequestMapping("/insecure_hashing/multiple_hash")
    String multipleInsecureHash() throws NoSuchAlgorithmException {
        return CryptoExamples.getSingleton().multipleInsecureHash(superSecretAccessKey);
    }

    @RequestMapping("/insecure_hashing/test_secure_algorithm")
    String secureHashing() throws NoSuchAlgorithmException {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return CryptoExamples.getSingleton().secureHashing(superSecretAccessKey);
    }

    @RequestMapping("/insecure_hashing/test_md5_algorithm")
    String insecureMd5Hashing() throws NoSuchAlgorithmException {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return CryptoExamples.getSingleton().insecureMd5Hashing(superSecretAccessKey);
    }

    @RequestMapping("/insecure_cipher/test_secure_algorithm")
    String secureCipher() throws NoSuchAlgorithmException, NoSuchPaddingException,
            IllegalBlockSizeException, BadPaddingException, InvalidKeyException {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return CryptoExamples.getSingleton().secureCipher(superSecretAccessKey);
    }

    @RequestMapping("/insecure_cipher/test_insecure_algorithm")
    String insecureCipher() throws NoSuchAlgorithmException, NoSuchPaddingException,
            IllegalBlockSizeException, BadPaddingException, InvalidKeyException {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return CryptoExamples.getSingleton().insecureCipher(superSecretAccessKey);
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
}
