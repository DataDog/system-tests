package com.datadoghq.system_tests.springboot;

import com.datadoghq.system_tests.springboot.iast.utils.CryptoExamples;
import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.security.NoSuchAlgorithmException;

@RestController
@RequestMapping("/iast/insecure_hashing")
public class AppSecIast {
    String superSecretAccessKey = "insecure";

    @RequestMapping("/deduplicate")
    String removeDuplicates() throws NoSuchAlgorithmException {
        return CryptoExamples.getSingleton().removeDuplicates(superSecretAccessKey);
    }

    @RequestMapping("/multiple_hash")
    String multipleInsecureHash() throws NoSuchAlgorithmException {
        return CryptoExamples.getSingleton().multipleInsecureHash(superSecretAccessKey);
    }

    @RequestMapping("/test_secure_algorithm")
    String secureHashing() throws NoSuchAlgorithmException {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return CryptoExamples.getSingleton().secureHashing(superSecretAccessKey);
    }

    @RequestMapping("/test_md5_algorithm")
    String insecureMd5Hashing() throws NoSuchAlgorithmException {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }
        return CryptoExamples.getSingleton().insecureMd5Hashing(superSecretAccessKey);
    }
}
