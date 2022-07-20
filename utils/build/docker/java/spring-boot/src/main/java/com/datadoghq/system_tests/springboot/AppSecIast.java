package com.datadoghq.system_tests.springboot;

import java.util.stream.Collectors;

import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.datadoghq.system_tests.springboot.iast.utils.CryptoExamples;

import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;

@RestController
public class AppSecIast {
	@RequestMapping("/iast/insecure_hashing")
	String insecureHashing(@RequestParam(required=false) String algorithmName) {
		
		String superSecretAccessKey = "insecure";
		
		final Span span = GlobalTracer.get().activeSpan();
		if (span != null) {
			span.setTag("appsec.event", true);
		}
		
		String result = "";
		CryptoExamples.InsecureHashingAlgorithm hashingAlgorithm = CryptoExamples.InsecureHashingAlgorithm.getEnum(algorithmName); 
		if(hashingAlgorithm == null ){
			result = CryptoExamples.InsecureHashingAlgorithm.stream()
					 .map(x -> CryptoExamples.getSingleton().traceDebugInsecureHash(x, superSecretAccessKey))
					 .collect(Collectors.joining("<br/>"));
		}else{
			result = CryptoExamples.getSingleton().traceDebugInsecureHash(hashingAlgorithm, superSecretAccessKey);
		}

		return result;
	}
}
