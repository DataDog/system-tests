package com.datadoghq.system_tests.springboot.iast.utils;

import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.Security;
import java.util.stream.Stream;

import javax.xml.bind.DatatypeConverter;

import org.bouncycastle.jce.provider.BouncyCastleProvider;

public class CryptoExamples {

	private static CryptoExamples singleton;
	
	private CryptoExamples() {
		
	}
	
	public static CryptoExamples getSingleton() {
		if(singleton == null) {
			//Needed for MD4 implementation
			Security.addProvider(new BouncyCastleProvider());
			singleton = new CryptoExamples();
		}
		return singleton;
	}
	
	public String createInsecureHash(InsecureHashingAlgorithm alg, String password) {
		String createdHash = null;
		
		try {
			MessageDigest md = MessageDigest.getInstance(alg.getAlgorithmName());
			md.update(password.getBytes());
			byte[] digest = md.digest();
			createdHash = DatatypeConverter.printHexBinary(digest).toUpperCase();
		} catch (NoSuchAlgorithmException e) {
			e.printStackTrace();
		}
		return createdHash;
	}


	public static enum InsecureHashingAlgorithm {
		SHA("SHA-1"), MD5("MD5"), MD4("MD4"), MD2("MD2");

		String algorithm;

		InsecureHashingAlgorithm(String algorithm) {
			this.algorithm = algorithm;
		}

		public static Stream<InsecureHashingAlgorithm> stream() {
			return Stream.of(InsecureHashingAlgorithm.values());
		}

		public String getAlgorithmName() {
			return this.algorithm;
		}
	}
}
