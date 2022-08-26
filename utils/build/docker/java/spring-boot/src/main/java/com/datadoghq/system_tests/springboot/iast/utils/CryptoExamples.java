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
		if (singleton == null) {
			// Needed for MD4 implementation
			Security.addProvider(new BouncyCastleProvider());
			singleton = new CryptoExamples();
		}
		return singleton;
	}

	public String createInsecureHash(HashingAlgorithm alg, String password) {
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

	public String traceDebugInsecureHash(HashingAlgorithm alg, String password) {
		return alg.getAlgorithmName() + ":" + CryptoExamples.getSingleton().createInsecureHash(alg, password);
	}

	public static enum HashingAlgorithm {
		sha1("SHA-1"), md5("MD5"), md4("MD4"), md2("MD2"),sha256("SHA-256");

		String algorithm;

		HashingAlgorithm(String algorithm) {
			this.algorithm = algorithm;
		}

		public static Stream<HashingAlgorithm> stream() {
			return Stream.of(HashingAlgorithm.values());
		}

		public static HashingAlgorithm getEnum(String value) {
			try {
				return HashingAlgorithm.valueOf(value);
			} catch (IllegalArgumentException|NullPointerException e) {
				return null;
			}
		}

		public String getAlgorithmName() {
			return this.algorithm;
		}

	}
}
