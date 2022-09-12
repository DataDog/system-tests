package com.datadoghq.system_tests.springboot;

import java.util.stream.Collectors;

import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.datadoghq.system_tests.springboot.iast.utils.CryptoExamples;

import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;

@RestController
@RequestMapping("/iast/insecure_hashing")
public class AppSecIast {
	String superSecretAccessKey = "insecure";
	
	@RequestMapping("/deduplicate")
	String removeDuplicates() {
		String result =   CryptoExamples.getSingleton().traceInsecureHash("md5", superSecretAccessKey) ;
		result +=  CryptoExamples.getSingleton().traceInsecureHash("sha1", superSecretAccessKey);
		return result;
	}

	@RequestMapping("/multiple_hash")
	String multipleInsecureHash() {
		return CryptoExamples.getSingleton().traceMultipleInsecureHash(superSecretAccessKey);
	}

	@RequestMapping("/test_secure_algorithm")
	String secureHashing() {
	
		final Span span = GlobalTracer.get().activeSpan();
		if (span != null) {
			span.setTag("appsec.event", true);
		}

		return CryptoExamples.getSingleton().traceInsecureHash("sha256", superSecretAccessKey);
	}

	@RequestMapping("/test_md5_algorithm")
	String insecureMd5Hashing() {

		final Span span = GlobalTracer.get().activeSpan();
		if (span != null) {
			span.setTag("appsec.event", true);
		}

		return CryptoExamples.getSingleton().traceInsecureHash("md5", superSecretAccessKey);
	}
}
