package com.datadoghq.system_tests.springboot.iast.utils;

import org.bouncycastle.jce.provider.BouncyCastleProvider;

import javax.crypto.BadPaddingException;
import javax.crypto.Cipher;
import javax.crypto.IllegalBlockSizeException;
import javax.crypto.KeyGenerator;
import javax.crypto.NoSuchPaddingException;
import javax.crypto.SecretKey;
import javax.xml.bind.DatatypeConverter;
import java.security.InvalidKeyException;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.Security;
import java.util.Arrays;

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

    public String removeDuplicates(final String password) throws NoSuchAlgorithmException {
        final StringBuilder builder = new StringBuilder();
        for (final String algorithm : Arrays.asList("md5", "sha1")) {
            final MessageDigest md = MessageDigest.getInstance(algorithm);
            builder.append(consumeMessageDigest(md, password));
        }
        return builder.toString();
    }

    public String multipleInsecureHash(final String password) throws NoSuchAlgorithmException {
        final MessageDigest md5 = MessageDigest.getInstance("md5");
        //TODO change MD4 to SHA1 when supported
        final MessageDigest md4 = MessageDigest.getInstance("md4");
        final StringBuilder builder = new StringBuilder();
        for (final MessageDigest md : Arrays.asList(md5, md4)) {
            builder.append(consumeMessageDigest(md, password));
        }
        return builder.toString();
    }

    public String secureHashing(final String password) throws NoSuchAlgorithmException {
        final MessageDigest sha256 = MessageDigest.getInstance("sha256");
        return consumeMessageDigest(sha256, password);
    }

    public String insecureMd5Hashing(final String password) throws NoSuchAlgorithmException {
        final MessageDigest md5 = MessageDigest.getInstance("md5");
        return consumeMessageDigest(md5, password);
    }

    public String insecureCipher(final String password) throws NoSuchPaddingException, NoSuchAlgorithmException, InvalidKeyException, IllegalBlockSizeException, BadPaddingException {
        return doCipher(password, "Blowfish");
    }

    public String secureCipher(final String password) throws NoSuchPaddingException, NoSuchAlgorithmException, InvalidKeyException, IllegalBlockSizeException, BadPaddingException {
        return doCipher(password, "AES");
    }

    private static String doCipher(final String password, final String algorithm) throws NoSuchAlgorithmException, NoSuchPaddingException, InvalidKeyException, IllegalBlockSizeException, BadPaddingException {
        KeyGenerator keygenerator = KeyGenerator.getInstance(algorithm);
        SecretKey key = keygenerator.generateKey();
        Cipher cipher = Cipher.getInstance(algorithm);
        cipher.init(Cipher.ENCRYPT_MODE, key);
        return new String(cipher.doFinal(password.getBytes()));
    }

    private String consumeMessageDigest(final MessageDigest md, final String password) {
        md.update(password.getBytes());
        byte[] digest = md.digest();
        return "[" + md.getAlgorithm() + ":" + DatatypeConverter.printHexBinary(digest).toUpperCase() + "]";
    }
}
