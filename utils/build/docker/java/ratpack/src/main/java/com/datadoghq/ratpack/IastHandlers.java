package com.datadoghq.ratpack;

import com.datadoghq.system_tests.iast.utils.CmdExamples;
import com.datadoghq.system_tests.iast.utils.CryptoExamples;
import com.datadoghq.system_tests.iast.utils.WeakRandomnessExamples;
import com.datadoghq.system_tests.iast.utils.XPathExamples;
import ratpack.handling.Chain;

public class IastHandlers {

    private final String superSecretAccessKey = "insecure";
    private final CmdExamples cmdExamples = new CmdExamples();
    private final CryptoExamples cryptoExamples = new CryptoExamples();
    private final WeakRandomnessExamples weakRandomnessExamples = new WeakRandomnessExamples();
    private final XPathExamples xPathExamples = new XPathExamples();

    public void setup(Chain chain) {
        chain
                .path("iast/insecure_hashing/deduplicate", ctx -> ctx.getResponse().send(cryptoExamples.removeDuplicates(superSecretAccessKey)))
                .path("iast/insecure_hashing/multiple_hash", ctx -> ctx.getResponse().send(cryptoExamples.multipleInsecureHash(superSecretAccessKey)))
                .path("iast/insecure_hashing/test_secure_algorithm", ctx -> ctx.getResponse().send(cryptoExamples.secureHashing(superSecretAccessKey)))
                .path("iast/insecure_hashing/test_md5_algorithm", ctx -> ctx.getResponse().send(cryptoExamples.insecureMd5Hashing(superSecretAccessKey)))
                .path("iast/insecure_cipher/test_secure_algorithm", ctx -> ctx.getResponse().send(cryptoExamples.secureCipher(superSecretAccessKey)))
                .path("iast/insecure_cipher/test_insecure_algorithm", ctx -> ctx.getResponse().send(cryptoExamples.insecureCipher(superSecretAccessKey)))
                .path("iast/weak_randomness/test_insecure", ctx -> ctx.getResponse().send(weakRandomnessExamples.weakRandom()))
                .path("iast/weak_randomness/test_secure", ctx -> ctx.getResponse().send(weakRandomnessExamples.secureRandom()))
                .path("iast/xpathi/test_insecure", ctx -> ctx.getResponse().send(xPathExamples.insecureXPath(ctx.getRequest().getQueryParams().get("expression"))))
                .path("iast/xpathi/test_secure", ctx -> ctx.getResponse().send(xPathExamples.secureXPath()))
                .post("iast/cmdi/test_insecure", ctx -> {
                    String cmd = ctx.getRequest().getForm().get("cmd");
                    ctx.getResponse().send(cmdExamples.insecureCmd(cmd));
                })
                .post("iast/cmdi/test_secure", ctx -> {
                    ctx.getResponse().send("Command executed: ls");
                });
    }

}
