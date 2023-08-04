package com.datadoghq.system_tests.iast.utils;

import org.bouncycastle.jce.provider.BouncyCastleProvider;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.xml.bind.DatatypeConverter;
import java.lang.reflect.UndeclaredThrowableException;
import java.security.MessageDigest;
import java.security.Security;
import java.util.Arrays;

public class CryptoExamples {

    static {
        Security.addProvider(new BouncyCastleProvider());
    }

    public String removeDuplicates(final String password) {
        try {
            final StringBuilder builder = new StringBuilder();
            for (final String algorithm : Arrays.asList("md5", "sha1")) {
                final MessageDigest md = MessageDigest.getInstance(algorithm);
                builder.append(consumeMessageDigest(md, password));
            }
            return builder.toString();
        } catch (final Exception e) {
            throw new UndeclaredThrowableException(e);
        }
    }

    public String multipleInsecureHash(final String password) {
        try {
            final MessageDigest md5 = MessageDigest.getInstance("md5");
            //TODO change MD4 to SHA1 when supported
            final MessageDigest md4 = MessageDigest.getInstance("md4");
            final StringBuilder builder = new StringBuilder();
            for (final MessageDigest md : Arrays.asList(md5, md4)) {
                builder.append(consumeMessageDigest(md, password));
            }
            return builder.toString();
        } catch (final Exception e) {
            throw new UndeclaredThrowableException(e);
        }
    }

    public String secureHashing(final String password) {
        try {
            final MessageDigest sha256 = MessageDigest.getInstance("sha256");
            return consumeMessageDigest(sha256, password);
        } catch (final Exception e) {
            throw new UndeclaredThrowableException(e);
        }
    }

    public String insecureMd5Hashing(final String password) {
        try {
            final MessageDigest md5 = MessageDigest.getInstance("md5");
            return consumeMessageDigest(md5, password);
        } catch (final Exception e) {
            throw new UndeclaredThrowableException(e);
        }
    }

    public String insecureCipher(final String password) {
        return doCipher(password, "Blowfish");
    }

    public String secureCipher(final String password) {
        return doCipher(password, "AES");
    }

    private static String doCipher(final String password, final String algorithm) {
        try {
            Cipher cipher = Cipher.getInstance(algorithm);
            cipher.init(Cipher.ENCRYPT_MODE, KeyGenerator.getInstance(algorithm).generateKey());
            return new String(cipher.doFinal(password.getBytes()));
        } catch (final Exception e) {
            throw new UndeclaredThrowableException(e);
        }
    }

    private String consumeMessageDigest(final MessageDigest md, final String password) {
        md.update(password.getBytes());
        byte[] digest = md.digest();
        return "[" + md.getAlgorithm() + ":" + DatatypeConverter.printHexBinary(digest).toUpperCase() + "]";
    }
}
