package com.datadoghq.system_tests.iast.utils;


import javax.naming.NamingEnumeration;
import javax.naming.directory.Attributes;
import javax.naming.directory.InitialDirContext;
import javax.naming.directory.SearchResult;
import java.lang.reflect.UndeclaredThrowableException;

public class LDAPExamples {

    private final InitialDirContext initialDirContext;

    public LDAPExamples(final InitialDirContext context) {
        this.initialDirContext = context;
    }

    public String injection(final String username, final String password) {
        final String filter = "(&(uid=" + username + ")(userPassword=" + password + "))";
        return getLdapUser(filter);
    }

    public String secure() {
        return getLdapUser("(&(uid=ben)(userPassword=benPass))");
    }

    private String getLdapUser(final String filter) {
        try {
            NamingEnumeration<?> namingEnum = this.initialDirContext.search("ou=people", filter, null);
            if (namingEnum.hasMore()) {
                SearchResult result = (SearchResult) namingEnum.next();
                Attributes attrs = result.getAttributes();
                return attrs.get("cn").toString();
            }
            return "";
        } catch (final Exception e) {
            throw new UndeclaredThrowableException(e);
        }
    }
}
