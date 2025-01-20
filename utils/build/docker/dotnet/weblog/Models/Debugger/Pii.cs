using System;

namespace weblog.Models.Debugger
{
    public abstract class PiiBase
    {
        public static string Value = "SHOULD_BE_REDACTED";
        public string? TestValue { get; set; } = Value;
    }

    public class Pii : PiiBase
    {
        public string? _2fa { get; set; } = PiiBase.Value;
        public string? ACCESSTOKEN { get; set; } = PiiBase.Value;
        public string? Access_Token { get; set; } = PiiBase.Value;
        public string? AccessToken { get; set; } = PiiBase.Value;
        public string? accessToken { get; set; } = PiiBase.Value;
        public string? access_token { get; set; } = PiiBase.Value;
        public string? accesstoken { get; set; } = PiiBase.Value;
        public string? aiohttpsession { get; set; } = PiiBase.Value;
        public string? apikey { get; set; } = PiiBase.Value;
        public string? apisecret { get; set; } = PiiBase.Value;
        public string? apisignature { get; set; } = PiiBase.Value;
        public string? appkey { get; set; } = PiiBase.Value;
        public string? applicationkey { get; set; } = PiiBase.Value;
        public string? auth { get; set; } = PiiBase.Value;
        public string? authorization { get; set; } = PiiBase.Value;
        public string? authtoken { get; set; } = PiiBase.Value;
        public string? ccnumber { get; set; } = PiiBase.Value;
        public string? certificatepin { get; set; } = PiiBase.Value;
        public string? cipher { get; set; } = PiiBase.Value;
        public string? clientid { get; set; } = PiiBase.Value;
        public string? clientsecret { get; set; } = PiiBase.Value;
        public string? connectionstring { get; set; } = PiiBase.Value;
        public string? connectsid { get; set; } = PiiBase.Value;
        public string? cookie { get; set; } = PiiBase.Value;
        public string? credentials { get; set; } = PiiBase.Value;
        public string? creditcard { get; set; } = PiiBase.Value;
        public string? csrf { get; set; } = PiiBase.Value;
        public string? csrftoken { get; set; } = PiiBase.Value;
        public string? cvv { get; set; } = PiiBase.Value;
        public string? databaseurl { get; set; } = PiiBase.Value;
        public string? dburl { get; set; } = PiiBase.Value;
        public string? encryptionkey { get; set; } = PiiBase.Value;
        public string? encryptionkeyid { get; set; } = PiiBase.Value;
        public string? geolocation { get; set; } = PiiBase.Value;
        public string? gpgkey { get; set; } = PiiBase.Value;
        public string? ipaddress { get; set; } = PiiBase.Value;
        public string? jti { get; set; } = PiiBase.Value;
        public string? jwt { get; set; } = PiiBase.Value;
        public string? licensekey { get; set; } = PiiBase.Value;
        public string? masterkey { get; set; } = PiiBase.Value;
        public string? mysqlpwd { get; set; } = PiiBase.Value;
        public string? nonce { get; set; } = PiiBase.Value;
        public string? oauth { get; set; } = PiiBase.Value;
        public string? oauthtoken { get; set; } = PiiBase.Value;
        public string? otp { get; set; } = PiiBase.Value;
        public string? passhash { get; set; } = PiiBase.Value;
        public string? passwd { get; set; } = PiiBase.Value;
        public string? password { get; set; } = PiiBase.Value;
        public string? passwordb { get; set; } = PiiBase.Value;
        public string? pemfile { get; set; } = PiiBase.Value;
        public string? pgpkey { get; set; } = PiiBase.Value;
        public string? phpsessid { get; set; } = PiiBase.Value;
        public string? pin { get; set; } = PiiBase.Value;
        public string? pincode { get; set; } = PiiBase.Value;
        public string? pkcs8 { get; set; } = PiiBase.Value;
        public string? privatekey { get; set; } = PiiBase.Value;
        public string? publickey { get; set; } = PiiBase.Value;
        public string? pwd { get; set; } = PiiBase.Value;
        public string? recaptchakey { get; set; } = PiiBase.Value;
        public string? refreshtoken { get; set; } = PiiBase.Value;
        public string? routingnumber { get; set; } = PiiBase.Value;
        public string? salt { get; set; } = PiiBase.Value;
        public string? secret { get; set; } = PiiBase.Value;
        public string? secretkey { get; set; } = PiiBase.Value;
        public string? secrettoken { get; set; } = PiiBase.Value;
        public string? securityanswer { get; set; } = PiiBase.Value;
        public string? securitycode { get; set; } = PiiBase.Value;
        public string? securityquestion { get; set; } = PiiBase.Value;
        public string? serviceaccountcredentials { get; set; } = PiiBase.Value;
        public string? session { get; set; } = PiiBase.Value;
        public string? sessionid { get; set; } = PiiBase.Value;
        public string? sessionkey { get; set; } = PiiBase.Value;
        public string? setcookie { get; set; } = PiiBase.Value;
        public string? signature { get; set; } = PiiBase.Value;
        public string? signaturekey { get; set; } = PiiBase.Value;
        public string? sshkey { get; set; } = PiiBase.Value;
        public string? ssn { get; set; } = PiiBase.Value;
        public string? symfony { get; set; } = PiiBase.Value;
        public string? token { get; set; } = PiiBase.Value;
        public string? transactionid { get; set; } = PiiBase.Value;
        public string? twiliotoken { get; set; } = PiiBase.Value;
        public string? usersession { get; set; } = PiiBase.Value;
        public string? voterid { get; set; } = PiiBase.Value;
        public string? xapikey { get; set; } = PiiBase.Value;
        public string? xauthtoken { get; set; } = PiiBase.Value;
        public string? xcsrftoken { get; set; } = PiiBase.Value;
        public string? xforwardedfor { get; set; } = PiiBase.Value;
        public string? xrealip { get; set; } = PiiBase.Value;
        public string? xsrf { get; set; } = PiiBase.Value;
        public string? xsrftoken { get; set; } = PiiBase.Value;

        public string? customidentifier1 { get; set; } = PiiBase.Value;
        public string? customidentifier2 { get; set; } = PiiBase.Value;
    }

    public class CustomPii : PiiBase
    {
        public string? customkey { get; set; } = PiiBase.Value;
    }
}
