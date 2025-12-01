class PiiBase:
    VALUE = "SHOULD_BE_REDACTED"

    def __init__(self):
        self.test_value = self.VALUE


class Pii(PiiBase):
    def __init__(self):
        super().__init__()
        self._2fa = self.VALUE
        self.ACCESSTOKEN = self.VALUE
        self.AccessToken = self.VALUE
        self.Access_Token = self.VALUE
        self.accessToken = self.VALUE
        self.access_token = self.VALUE
        self.accesstoken = self.VALUE
        self.aiohttpsession = self.VALUE
        self.apikey = self.VALUE
        self.apisecret = self.VALUE
        self.apisignature = self.VALUE
        self.appkey = self.VALUE
        self.applicationkey = self.VALUE
        self.auth = self.VALUE
        self.authorization = self.VALUE
        self.authtoken = self.VALUE
        self.ccnumber = self.VALUE
        self.certificatepin = self.VALUE
        self.cipher = self.VALUE
        self.clientid = self.VALUE
        self.clientsecret = self.VALUE
        self.connectionstring = self.VALUE
        self.connectsid = self.VALUE
        self.cookie = self.VALUE
        self.credentials = self.VALUE
        self.creditcard = self.VALUE
        self.csrf = self.VALUE
        self.csrftoken = self.VALUE
        self.cvv = self.VALUE
        self.databaseurl = self.VALUE
        self.dburl = self.VALUE
        self.encryptionkey = self.VALUE
        self.encryptionkeyid = self.VALUE
        self.geolocation = self.VALUE
        self.gpgkey = self.VALUE
        self.ipaddress = self.VALUE
        self.jti = self.VALUE
        self.jwt = self.VALUE
        self.licensekey = self.VALUE
        self.masterkey = self.VALUE
        self.mysqlpwd = self.VALUE
        self.nonce = self.VALUE
        self.oauth = self.VALUE
        self.oauthtoken = self.VALUE
        self.otp = self.VALUE
        self.passhash = self.VALUE
        self.passwd = self.VALUE
        self.password = self.VALUE
        self.passwordb = self.VALUE
        self.pemfile = self.VALUE
        self.pgpkey = self.VALUE
        self.phpsessid = self.VALUE
        self.pin = self.VALUE
        self.pincode = self.VALUE
        self.pkcs8 = self.VALUE
        self.privatekey = self.VALUE
        self.publickey = self.VALUE
        self.pwd = self.VALUE
        self.recaptchakey = self.VALUE
        self.refreshtoken = self.VALUE
        self.routingnumber = self.VALUE
        self.salt = self.VALUE
        self.secret = self.VALUE
        self.secretkey = self.VALUE
        self.secrettoken = self.VALUE
        self.securityanswer = self.VALUE
        self.securitycode = self.VALUE
        self.securityquestion = self.VALUE
        self.serviceaccountcredentials = self.VALUE
        self.session = self.VALUE
        self.sessionid = self.VALUE
        self.sessionkey = self.VALUE
        self.setcookie = self.VALUE
        self.signature = self.VALUE
        self.signaturekey = self.VALUE
        self.sshkey = self.VALUE
        self.ssn = self.VALUE
        self.symfony = self.VALUE
        self.token = self.VALUE
        self.transactionid = self.VALUE
        self.twiliotoken = self.VALUE
        self.usersession = self.VALUE
        self.voterid = self.VALUE
        self.xapikey = self.VALUE
        self.xauthtoken = self.VALUE
        self.xcsrftoken = self.VALUE
        self.xforwardedfor = self.VALUE
        self.xrealip = self.VALUE
        self.xsrf = self.VALUE
        self.xsrftoken = self.VALUE

        self.customidentifier1 = self.VALUE
        self.customidentifier2 = self.VALUE


class CustomPii(PiiBase):
    def __init__(self):
        super().__init__()
        self.customkey = self.VALUE
