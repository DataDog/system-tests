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
function init (app, tracer) {  
  initData().catch(() => {})

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
    res.setHeader('set-cookie', 'secure=cookie; Secure')
    res.cookie('secure2', 'value', { secure: true })
    res.send('OK')
  });

  app.get('/iast/insecure-cookie/test_empty_cookie', (req, res) => {
    res.clearCookie('insecure')
    res.setHeader('set-cookie', 'empty=')
    res.cookie('secure2', '')
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

  require('./sources')(app, tracer);

}

module.exports = init;
