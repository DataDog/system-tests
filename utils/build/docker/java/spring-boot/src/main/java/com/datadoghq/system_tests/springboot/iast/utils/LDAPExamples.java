package com.datadoghq.system_tests.springboot.iast.utils;


import org.springframework.stereotype.Component;

import javax.naming.Context;
import javax.naming.NamingEnumeration;
import javax.naming.NamingException;
import javax.naming.directory.Attributes;
import javax.naming.directory.InitialDirContext;
import javax.naming.directory.SearchResult;
import java.util.Hashtable;

//@Component
public class LDAPExamples {

    InitialDirContext initialDirContext;

    public LDAPExamples() {
    }

    public String injection(final String username, final String password) throws NamingException {
        initContext();
        final String filter = "(&(uid="+username+")(userPassword="+password+"))";
        return getLdapUser(filter);
    }

    public String secure() throws NamingException {
        initContext();
        return getLdapUser("(&(uid=ben)(userPassword=benPass))");
    }

    private String getLdapUser(final String filter) throws NamingException {
        NamingEnumeration<?> namingEnum = this.initialDirContext.search("ou=people", filter, null);
        while (namingEnum.hasMore ()) {
            SearchResult result = (SearchResult) namingEnum.next ();
            Attributes attrs = result.getAttributes();
            return attrs.get("cn").toString();
        }
        return null;
    }

    private void initContext()  throws NamingException{
        if (this.initialDirContext == null){
            Hashtable env = new Hashtable(3);
            env.put(Context.INITIAL_CONTEXT_FACTORY, "com.sun.jndi.ldap.LdapCtxFactory");
            env.put(Context.PROVIDER_URL, "ldap://localhost:8389/dc=springframework,dc=org");
            env.put(Context.SECURITY_AUTHENTICATION, "none");
            this.initialDirContext = new InitialDirContext(env);
        }
    }
}
