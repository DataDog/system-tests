const REDACTED_KEYS = [
  '_2fa',
  'ACCESSTOKEN',
  'AccessToken',
  'Access_Token',
  'accessToken',
  'access_token',
  'accesstoken',
  'aiohttpsession',
  'apikey',
  'apisecret',
  'apisignature',
  'appkey',
  'applicationkey',
  'auth',
  'authorization',
  'authtoken',
  'ccnumber',
  'certificatepin',
  'cipher',
  'clientid',
  'clientsecret',
  'connectionstring',
  'connectsid',
  'cookie',
  'credentials',
  'creditcard',
  'csrf',
  'csrftoken',
  'cvv',
  'databaseurl',
  'dburl',
  'encryptionkey',
  'encryptionkeyid',
  'geolocation',
  'gpgkey',
  'ipaddress',
  'jti',
  'jwt',
  'licensekey',
  'masterkey',
  'mysqlpwd',
  'nonce',
  'oauth',
  'oauthtoken',
  'otp',
  'passhash',
  'passwd',
  'password',
  'passwordb',
  'pemfile',
  'pgpkey',
  'phpsessid',
  'pin',
  'pincode',
  'pkcs8',
  'privatekey',
  'publickey',
  'pwd',
  'recaptchakey',
  'refreshtoken',
  'routingnumber',
  'salt',
  'secret',
  'secretkey',
  'secrettoken',
  'securityanswer',
  'securitycode',
  'securityquestion',
  'serviceaccountcredentials',
  'session',
  'sessionid',
  'sessionkey',
  'setcookie',
  'signature',
  'signaturekey',
  'sshkey',
  'ssn',
  'symfony',
  'token',
  'transactionid',
  'twiliotoken',
  'usersession',
  'voterid',
  'xapikey',
  'xauthtoken',
  'xcsrftoken',
  'xforwardedfor',
  'xrealip',
  'xsrf',
  'xsrftoken',
  'customidentifier1',
  'customidentifier2'
]

const VALUE = 'SHOULD_BE_REDACTED'

export class Pii {
  [key: string]: string

  constructor () {
    REDACTED_KEYS.forEach((key) => {
      this[key] = VALUE
    })
  }
}
