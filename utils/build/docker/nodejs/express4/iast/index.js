'use strict'

const { Client, Pool } = require('pg')
const { readFileSync, statSync } = require('fs')
const { join } = require('path')
const crypto = require('crypto');
const { execSync } = require('child_process');
const https = require('http');

function initData () {
  const query = readFileSync(join(__dirname, '..', 'resources', 'iast-data.sql')).toString()
  const client = new Client()
  return client.connect().then(() => {
    return client.query(query)
  })
}

function initMiddlewares (app) {
  const hstsMissingInsecurePattern = /.*hsts-missing-header\/test_insecure$/gmi
  const xcontenttypeMissingInsecurePattern = /.*xcontenttype-missing-header\/test_insecure$/gmi
  app.use((req, res, next) => {
    if (!req.url.match(hstsMissingInsecurePattern)) {
      res.setHeader('Strict-Transport-Security', 'max-age=31536000')
    }
    if (!req.url.match(xcontenttypeMissingInsecurePattern)) {
      res.setHeader('X-Content-Type-Options', 'nosniff')
    }
    next()
  })
}

function initRoutes (app, tracer) {  
  app.get('/iast/insecure_hashing/deduplicate', (req, res) => {
    const span = tracer.scope().active();
    span.setTag('appsec.event"', true);
  
    var supportedAlgorithms = [ 'md5', 'sha1' ];
  
    var outputHashes = "";
    supportedAlgorithms.forEach(algorithm => {
      var hash = crypto.createHash(algorithm).update('insecure').digest('hex')
      outputHashes += `--- ${algorithm}:${hash} ---`
    });
  
    res.send(outputHashes);
  });
  
  app.get('/iast/insecure_hashing/multiple_hash', (req, res) => {
    const span = tracer.scope().active();
    span.setTag('appsec.event"', true);
  
    const name = 'insecure';
    var outputHashes = crypto.createHash('md5').update(name).digest('hex');
    outputHashes += `--- ` + crypto.createHash('sha1').update(name).digest('hex')
  
    res.send(outputHashes);
  });
  
  app.get('/iast/insecure_hashing/test_secure_algorithm', (req, res) => {
    const span = tracer.scope().active();
    span.setTag('appsec.event"', true);
  
    res.send(crypto.createHash('sha256').update('secure').digest('hex'));
  });
  
  
  app.get('/iast/insecure_hashing/test_md5_algorithm', (req, res) => {
    const span = tracer.scope().active();
    span.setTag('appsec.event"', true);
  
    console.error('/iast/insecure_hashing/test_md5_algorithm')
    res.send(crypto.createHash('md5').update('insecure').digest('hex'));
  });
  
  app.get('/iast/insecure_cipher/test_insecure_algorithm', (req, res) => {
    const span = tracer.scope().active();
    span.setTag('appsec.event"', true);
    const cipher = crypto.createCipheriv('des-ede-cbc', '1111111111111111', 'abcdefgh')
    res.send(Buffer.concat([cipher.update('12345'), cipher.final()]))
  });
  
  app.get('/iast/insecure_cipher/test_secure_algorithm', (req, res) => {
    const span = tracer.scope().active();
    span.setTag('appsec.event"', true);
    const cipher = crypto.createCipheriv('sha256', '1111111111111111', 'abcdefgh')
    res.send(Buffer.concat([cipher.update('12345'), cipher.final()]))
  });
  
  app.post('/iast/sqli/test_insecure', (req, res) => {
    const span = tracer.scope().active();
    span.setTag('appsec.event"', true);
    const sql = 'SELECT * FROM IAST_USER WHERE USERNAME = \'' + req.body.username + '\' AND PASSWORD = \'' + req.body.password + '\''  
    const client = new Client()
    client.connect().then(() => {
      return client.query(sql).then((queryResult) => {
        res.json(queryResult)
      })
    }).catch((err) => {
      res.status(500).json({message: 'Error on request'})
    })
  });
  
  app.post('/iast/sqli/test_secure', (req, res) => {
    const span = tracer.scope().active();
    span.setTag('appsec.event"', true);
    const sql = 'SELECT * FROM IAST_USER WHERE USERNAME = $1 AND PASSWORD = $2'  
    const values = [req.body.username, req.body.password]
    const client = new Client()
    client.connect().then(() => {
      return client.query(sql, values).then((queryResult) => {
        res.json(queryResult)
      })
    }).catch((err) => {
      res.status(500).json({message: 'Error on request'})
    })
  });

  app.post('/iast/cmdi/test_insecure', (req, res) => {
    const result = execSync(req.body.cmd)
    res.send(result.toString())
  });

  app.post('/iast/path_traversal/test_insecure', (req, res) => {
    const span = tracer.scope().active();
    span.setTag('appsec.event"', true);
    const stats = statSync(req.body.path)
    res.send(JSON.stringify(stats))
  });

  app.post('/iast/ssrf/test_insecure', (req, res) => {
    https.get(req.body.url, () => {
      res.send('OK')
    })
  });


  app.get('/iast/insecure-cookie/test_insecure', (req, res) => {
    res.cookie('insecure', 'cookie')
    res.send('OK')
  });

  app.get('/iast/insecure-cookie/test_secure', (req, res) => {
    res.setHeader('set-cookie', 'secure=cookie; Secure; HttpOnly; SameSite=Strict')
    res.cookie('secure2', 'value', { secure: true, httpOnly: true, sameSite: true })
    res.send('OK')
  });

  app.get('/iast/insecure-cookie/test_empty_cookie', (req, res) => {
    res.clearCookie('insecure')
    res.setHeader('set-cookie', 'empty=')
    res.cookie('secure3', '')
    res.send('OK')
  });

  app.get('/iast/no-httponly-cookie/test_insecure', (req, res) => {
    res.cookie('no-httponly', 'cookie')
    res.send('OK')
  });

  app.get('/iast/no-httponly-cookie/test_secure', (req, res) => {
    res.setHeader('set-cookie', 'httponly=cookie; Secure;HttpOnly;SameSite=Strict;')
    res.cookie('httponly2', 'value', { secure: true, httpOnly: true, sameSite: true })
    res.send('OK')
  });

  app.get('/iast/no-httponly-cookie/test_empty_cookie', (req, res) => {
    res.clearCookie('insecure')
    res.setHeader('set-cookie', 'httponlyempty=')
    res.cookie('httponlyempty2', '')
    res.send('OK')
  });

  app.get('/iast/no-samesite-cookie/test_insecure', (req, res) => {
    res.cookie('nosamesite', 'cookie')
    res.send('OK')
  });

  app.get('/iast/no-samesite-cookie/test_secure', (req, res) => {
    res.setHeader('set-cookie', 'samesite=cookie; Secure; HttpOnly; SameSite=Strict')
    res.cookie('samesite2', 'value', { secure: true, httpOnly: true, sameSite: true })
    res.send('OK')
  });

  app.get('/iast/no-samesite-cookie/test_empty_cookie', (req, res) => {
    res.clearCookie('insecure')
    res.setHeader('set-cookie', 'samesiteempty=')
    res.cookie('samesiteempty2', '')
    res.send('OK')
  });

  app.post('/iast/unvalidated_redirect/test_secure_header', (req, res) => {
    res.setHeader('location', 'http://dummy.location.com')
    res.send('OK')
  });

  app.post('/iast/unvalidated_redirect/test_insecure_header', (req, res) => {
    res.setHeader('location', req.body.location)
    res.send('OK')
  });

  app.post('/iast/unvalidated_redirect/test_secure_redirect', (req, res) => {
    res.redirect('http://dummy.location.com')
  });

  app.post('/iast/unvalidated_redirect/test_insecure_redirect', (req, res) => {
    res.redirect(req.body.location)
  });

  app.get('/iast/hsts-missing-header/test_insecure', (req, res) => {
    res.setHeader('Content-Type', 'text/html')
    res.end('<html><body><h1>Test</h1></html>')
  });

  app.get('/iast/hsts-missing-header/test_secure', (req, res) => {
    res.setHeader('Strict-Transport-Security', 'max-age=31536000')
    res.setHeader('X-Content-Type-Options', 'nosniff')
    res.send('<html><body><h1>Test</h1></html>')
  });

  app.get('/iast/xcontenttype-missing-header/test_insecure', (req, res) => {
    res.setHeader('Content-Type', 'text/html')
    res.end('<html><body><h1>Test</h1></html>')
  });

  app.get('/iast/xcontenttype-missing-header/test_secure', (req, res) => {
    res.send('<html><body><h1>Test</h1></html>')
  });

  require('./sources')(app, tracer);

}

module.exports = { initRoutes, initData, initMiddlewares };
