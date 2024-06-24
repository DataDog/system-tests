MITM use a self-signed certificate that allow traffic inspection. This certificate has an expiration date. If system tests are not working at all, and the stdout of one proxy says something like `The mitmproxy certificate authority has expired!`, you need to renew it. Don't panic, it's easy !

1. Run the build step
1. remove all the content of `utils/proxy/.mitmproxy`
1. run a scenario (it will fail)
1. `utils/proxy/.mitmproxy` should have new certificate (one `.cer` file, two `.p12` files and three `.pem` file)
1. update `utils/scripts/install_mitm_certificate.sh` with the content of `utils/proxy/.mitmproxy/mitmproxy-ca-cert.cer`

Et voila :tada:
