#!/bin/bash
# Re-issue the WebSphere SOAP/SSL personal certificate during the image build.
#
# The base image ships a self-signed "default" certificate with a 1-year
# validity. Once it expires, the wsadmin SOAP-over-SSL handshake fails with
# "PKIX path building failed: unable to find valid certification path to
# requested target" and the application deployment cannot run. We re-issue the
# certificate signed by the existing (long-lived, ~2040) root CA so the client
# truststore keeps trusting it without any further changes.
set -euo pipefail

WAS=/opt/IBM/WebSphere/AppServer
KT="${WAS}/java/8.0/bin/keytool"
CFG="${WAS}/profiles/AppSrv01/config/cells/DefaultCell01/nodes/DefaultNode01"
PW=WebAS
# keytool requires new key passwords to be at least 6 chars, but the WebSphere
# keystore password is 5 chars, so we mint the key in a temp store first.
TMP=changeit
DN="CN=localhost,OU=DefaultCell01,OU=DefaultNode01,O=IBM,C=US"
NEW=/tmp/new_default.p12

"${KT}" -genkeypair -alias default -dname "${DN}" -keyalg RSA -keysize 2048 \
  -sigalg SHA256withRSA -validity 7300 -keystore "${NEW}" -storepass "${TMP}" \
  -keypass "${TMP}" -storetype PKCS12
"${KT}" -certreq -alias default -keystore "${NEW}" -storepass "${TMP}" \
  -file /tmp/default.csr
"${KT}" -gencert -alias root -keystore "${CFG}/root-key.p12" -storepass "${PW}" \
  -storetype PKCS12 -infile /tmp/default.csr -outfile /tmp/default.cer \
  -validity 7300 -sigalg SHA256withRSA -rfc
"${KT}" -exportcert -alias root -keystore "${CFG}/root-key.p12" -storepass "${PW}" \
  -storetype PKCS12 -rfc -file /tmp/root.cer
"${KT}" -importcert -noprompt -alias root -file /tmp/root.cer -keystore "${NEW}" \
  -storepass "${TMP}" -storetype PKCS12
"${KT}" -importcert -noprompt -alias default -file /tmp/default.cer -keystore "${NEW}" \
  -storepass "${TMP}" -storetype PKCS12
"${KT}" -delete -alias default -keystore "${CFG}/key.p12" -storepass "${PW}" \
  -storetype PKCS12 || true
"${KT}" -importkeystore -noprompt -srckeystore "${NEW}" -srcstorepass "${TMP}" \
  -srcstoretype PKCS12 -srcalias default -destkeystore "${CFG}/key.p12" \
  -deststorepass "${PW}" -destkeypass "${PW}" -deststoretype PKCS12 -destalias default

echo "WebSphere SOAP/SSL certificate re-issued (signed by existing root CA)."
