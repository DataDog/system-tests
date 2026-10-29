`mocked-backend.pem` holds the certificate, and its key, the mocked backend uses when it serves HTTPS
(`--tls-cert-file`). It is signed by the mitmproxy CA (`utils/proxy/.mitmproxy`), trusted by the senders of HTTPS
scenarios. It covers the container name, the intake hostnames derived from the mock `DD_SITE`, and `localhost`.

To add a hostname, or before it expires (in 2036), regenerate it:

```bash
openssl req -new -newkey rsa:2048 -nodes -keyout key.pem -subj "/CN=mocked-backend" -out req.csr
echo "subjectAltName=DNS:mocked-backend,DNS:event-platform-intake.mock-intake.invalid,DNS:instrumentation-telemetry-intake.mock-intake.invalid,DNS:localhost,IP:127.0.0.1" > ext
openssl x509 -req -in req.csr -CA utils/proxy/.mitmproxy/mitmproxy-ca.pem -CAkey utils/proxy/.mitmproxy/mitmproxy-ca.pem \
    -set_serial 0x$(openssl rand -hex 8) -days 3650 -sha256 -extfile ext -out cert.pem
cat cert.pem key.pem > utils/mocked_backend/tls/mocked-backend.pem
```
