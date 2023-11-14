const path = require('path')
const os = require('os')
const crypto = require('crypto')
const ldap = require('ldapjs')

const SUFFIX = 'ou=people'

function getSock () {
  const uuid = crypto.randomBytes(16).toString('hex')

  if (process.platform === 'win32') {
    return '\\\\.\\pipe\\' + uuid
  } else {
    return path.join(os.tmpdir(), uuid)
  }
}

let listening = false
let server
const socketPath = getSock()

async function getServer () {
  return new Promise((resolve, reject) => {
    if (listening) return resolve(server)

    server = ldap.createServer()

    server.bind(SUFFIX, (req, res, next) => {
      res.end()
      return next()
    })

    server.search(SUFFIX, function (req, res, next) {
      const obj = {
        dn: req.dn.toString(),
        attributes: {
          uid: 'ssam',
          password: 'sammy'
        }
      }

      if (req.filter.matches(obj.attributes)) {
        res.send(obj)
      }

      res.end()
      return next()
    })

    server.on('error', reject)

    server.listen(socketPath, () => {
      listening = true
      resolve(server)
    })
  })
}

async function connect () {
  return getServer().then(() => {
    return new Promise((resolve, reject) => {
      const client = ldap.createClient({
        connectTimeout: 0,
        socketPath
      })

      client.on('error', (err) => reject(err))
      client.on('connect', () => resolve(client))
    })
  })
}

module.exports = {
  connect
}
