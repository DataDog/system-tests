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

	public String createInsecureHash(String alg, String password) {
		String createdHash = null;

		try {
			MessageDigest md = MessageDigest.getInstance(alg);
			md.update(password.getBytes());
			byte[] digest = md.digest();
			createdHash = DatatypeConverter.printHexBinary(digest).toUpperCase();
		} catch (NoSuchAlgorithmException e) {
			e.printStackTrace();
		}
		return createdHash;
	}

	public String traceInsecureHash(String  alg, String password) {
		return "[" + alg + ":" + CryptoExamples.getSingleton().createInsecureHash(alg, password) + "]";
	}

	public String traceMultipleInsecureHash( String password) {
		String createdHash = "";
		try {
			MessageDigest md = MessageDigest.getInstance("md5");
			md.update(password.getBytes());
			byte[] digest = md.digest();
			createdHash = "[md5:" + DatatypeConverter.printHexBinary(digest).toUpperCase() + "]"; 

			//TODO change MD4 to SHA1 when supported
			md = MessageDigest.getInstance("md4");
			md.update(password.getBytes());
			digest = md.digest();
			createdHash += "[md4:" + DatatypeConverter.printHexBinary(digest).toUpperCase() + "]";
		} catch (NoSuchAlgorithmException e) {
			e.printStackTrace();
		}
		return createdHash;
	}
}
