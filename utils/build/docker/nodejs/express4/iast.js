const { Client, Pool } = require('pg')
const { readFileSync } = require('fs')
const { join } = require('path')
const crypto = require('crypto');

function initData () {
  const query = readFileSync(join(__dirname, 'resources', 'iast-data.sql')).toString()
  const client = new Client()
  return client.connect().then(() => {
    return client.query(query)
  })
}
function init (app, tracer) {  
  initData()

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
  
    res.send(crypto.createHash('sha256').update('insecure').digest('hex'));
  });
  
  
  app.get('/iast/insecure_hashing/test_md5_algorithm', (req, res) => {
    const span = tracer.scope().active();
    span.setTag('appsec.event"', true);
    console.log('insecure_hashing/test_md5_algorithm')
    crypto.createHash('md5-sha1').update('aaa').digest('hex')
  
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
      client.query(sql).then((queryResult) => {
        res.json(queryResult)
      }).catch((err) => {
        res.status(500).json({message: 'Error on request'})
      })
    })
  });
  
  app.post('/iast/sqli/test_secure', (req, res) => {
    const span = tracer.scope().active();
    span.setTag('appsec.event"', true);
    const sql = 'SELECT * FROM IAST_USER WHERE USERNAME = $1 AND PASSWORD = $2'  
    const values = [req.body.username, req.body.password]
    const client = new Client()
    client.connect().then(() => {
      client.query(sql, values).then((queryResult) => {
        res.json(queryResult)
      }).catch((err) => {
        res.status(500).json({message: 'Error on request'})
      })
    })
  });

}

module.exports = init;