package com.datadoghq.system_tests.iast.utils.mock;
import javax.mail.Message;
import javax.mail.MessagingException;
import javax.mail.Session;
import javax.mail.Transport;
import javax.mail.URLName;
import javax.mail.Address;
import java.util.Properties;

public class MockTransport extends Transport {
        public MockTransport(Session session, URLName urlname) {
            super(session, urlname);
        }

        public MockTransport() {
            this(Session.getInstance(new Properties()), null);
        }

        public MockTransport(Session session) {
            this(session, null);
        }

        public static Transport newInstance(Session session) {
            return new MockTransport(session, null);
        }

        public void sendMessage(Message msg, Address[] addresses) throws MessagingException {
            this.notifyTransportListeners(1, addresses, new Address[0], new Address[0], msg);

        }

        @Override
        public void connect() {
            this.setConnected(true);
            this.notifyConnectionListeners(1);
        }

        public synchronized void connect(String host, int port, String user, String password)
            throws MessagingException {}
    }