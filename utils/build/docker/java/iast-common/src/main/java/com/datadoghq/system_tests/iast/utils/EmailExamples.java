package com.datadoghq.system_tests.iast.utils;

import com.datadoghq.system_tests.iast.utils.mock.MockTransport;

import javax.mail.Message;
import javax.mail.MessagingException;
import javax.mail.Session;
import javax.mail.Provider;
import javax.mail.internet.InternetAddress;
import javax.mail.internet.MimeMessage;
import java.util.Properties;


public class EmailExamples {

    public void mail(final String emailContent) throws MessagingException {
        Session session = Session.getDefaultInstance(new Properties());
        Provider provider =
                new Provider(
                        Provider.Type.TRANSPORT, "smtp", MockTransport.class.getName(), "MockTransport", "1.0");
        session.setProvider(provider);
        Message email = new MimeMessage(session);
        email.setContent(emailContent, "text/html");
        email.setRecipient(Message.RecipientType.TO, new InternetAddress("abc@datadoghq.com"));

        MockTransport.send(email);

    }


}
