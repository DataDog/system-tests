package com.datadoghq.system_tests.springboot;

import java.util.stream.Collectors;

import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.datadoghq.system_tests.springboot.iast.utils.CryptoExamples;

import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;

@RestController
public class AppSecIast {
	@RequestMapping("/iast/insecure_hashing")
	String insecureHashing() {
		
		String superSecretAccessKey = "insecure";
		
		final Span span = GlobalTracer.get().activeSpan();
		if (span != null) {
			span.setTag("appsec.event", true);
		}

		return CryptoExamples.InsecureHashingAlgorithm.stream()
				.map(x -> x.getAlgorithmName() + ":" + CryptoExamples.getSingleton().createInsecureHash(x, superSecretAccessKey))
				.collect(Collectors.joining("<br/>"));

	}
}
