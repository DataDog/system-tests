<?php

class DebuggerController {
    function logProbe() {
        return "Log probe";
    }

    function metricProbe(int $id) {
        ++$id;
        return "Metric Probe $id";
    }

    function spanProbe() {
        return "Span probe";
    }

    function spanDecorationProbe(string $arg, int $intArg) {
        $intLocal = $intArg * strlen($arg);
        return "Span Decoration Probe {$intLocal}";
    }

    private $intMixLocal = 0;
    function mixProbe(string $arg, int $intArg) {
        $this->intMixLocal = $intArg * strlen($arg);
        return "Mixed result {$this->intLocal}";
    }

    function pii() {
        $pii = new Pii;
        $customPii = new CustomPii;
        $value = $pii->TestValue;
        $customValue = $customPii->TestValue;
        return "PII $value. CustomPii: $customValue";
    }

    function expression(string $inputValue) {
        $testStruct = new ExpressionTestStruct;
        $localValue = strlen($inputValue);
        return "Great success number $localValue";
    }

    function expressionException() {
        throw new \Exception("Hello from exception");
    }

    function expressionOperators(int $intValue, float $floatValue, string $strValue) {
        return "Int value $intValue. Float value $floatValue. String value is $strValue";
    }

    function expressionStrings(string $strValue, string $emptyString = "", $nullString = null) {
        return "strValue $strValue. emptyString $emptyString. nullString $nullString";
    }

    function expressionCollectionOperations() {
        $a0 = [];
        $l0 = [];
        $h0 = [];
        $a1 = range(0, 0);
        $l1 = range(0, 0);
        $h1 = range(0, 0);
        $a5 = range(0, 4);
        $l5 = range(0, 4);
        $h5 = range(0, 4);

        return count($a0) . ", " . count($a1) . "," . count($a5) . "," . count($l0) . "," . count($l1) . "," . count($l5) . "," . count($h0) . "," . count($h1) . "," . count($h5) . ".";
    }

    function expressionNulls(int $intValue = null, string $strValue = null) {
        $pii = null;

        return "Pii is null " . ($pii === null) .
                ". intValue is null " . ($intValue === null) .
                ". strValue is null " . ($strValue === null) . ".";
    }

    function exceptionReplaySimple() {
        throw new \Exception("Simple exception");
    }

    function exceptionReplayRecursion5($depth = 5) {
        if ($depth > 0) {
            return $this->exceptionReplayRecursion5($depth - 1);
        } else {
            throw new \Exception("Recursion exception");
        }
    }

    function exceptionReplayRecursion20($depth = 20) {
        if ($depth > 0) {
            return $this->exceptionReplayRecursion20($depth - 1);
        } else {
            throw new \Exception("Recursion exception");
        }
    }

    public function exceptionReplayInner() {
        try {
            throw new \Exception("Inner exception");
        } catch (Exception $ex) {
            throw new \Exception("Outer exception", 0, $ex);
        }
    }
}

if (empty($skipExecution)) {
    $args = explode("/", substr($_SERVER["PATH_INFO"], 1));
    $method = strtr(array_shift($args), ["_" => "", "-" => ""]);
    $c = new DebuggerController;
    if (!method_exists($c, $method)) {
        $method .= "Probe";
    }
    foreach ((new ReflectionMethod($c, $method))->getParameters() as $param) {
        if (isset($_GET[$param->name])) {
            $args[] = $_GET[$param->name];
        }
    }
    echo $c->$method(...$args);
}

class ExpressionTestStruct {
    public $IntValue = 1;
    public $DoubleValue = 1.1;
    public $StringValue = "one";
    public $BoolValue = true;

    public $Collection = ["one", "two", "three"];
    public $Dictionary = ["one" => 1, "two" => 2, "three" => 3, "four" => 4];
}

abstract class PiiBase {
    const Value = "SHOULD_BE_REDACTED";
    public $TestValue = self::Value;
}

class Pii extends PiiBase {
    public $_2fa = parent::Value;
    public $accesstoken = parent::Value;
    public $access_token = parent::Value;
    public $Access_Token = parent::Value;
    public $accessToken = parent::Value;
    public $AccessToken = parent::Value;
    public $ACCESSTOKEN = parent::Value;
    public $aiohttpsession = parent::Value;
    public $apikey = parent::Value;
    public $apisecret = parent::Value;
    public $apisignature = parent::Value;
    public $applicationkey = parent::Value;
    public $auth = parent::Value;
    public $authorization = parent::Value;
    public $authtoken = parent::Value;
    public $ccnumber = parent::Value;
    public $certificatepin = parent::Value;
    public $cipher = parent::Value;
    public $clientid = parent::Value;
    public $clientsecret = parent::Value;
    public $connectionstring = parent::Value;
    public $connectsid = parent::Value;
    public $cookie = parent::Value;
    public $credentials = parent::Value;
    public $creditcard = parent::Value;
    public $csrf = parent::Value;
    public $csrftoken = parent::Value;
    public $cvv = parent::Value;
    public $databaseurl = parent::Value;
    public $dburl = parent::Value;
    public $encryptionkey = parent::Value;
    public $encryptionkeyid = parent::Value;
    public $env = parent::Value;
    public $geolocation = parent::Value;
    public $gpgkey = parent::Value;
    public $ipaddress = parent::Value;
    public $jti = parent::Value;
    public $jwt = parent::Value;
    public $licensekey = parent::Value;
    public $masterkey = parent::Value;
    public $mysqlpwd = parent::Value;
    public $nonce = parent::Value;
    public $oauth = parent::Value;
    public $oauthtoken = parent::Value;
    public $otp = parent::Value;
    public $passhash = parent::Value;
    public $passwd = parent::Value;
    public $password = parent::Value;
    public $passwordb = parent::Value;
    public $pemfile = parent::Value;
    public $pgpkey = parent::Value;
    public $phpsessid = parent::Value;
    public $pin = parent::Value;
    public $pincode = parent::Value;
    public $pkcs8 = parent::Value;
    public $privatekey = parent::Value;
    public $publickey = parent::Value;
    public $pwd = parent::Value;
    public $recaptchakey = parent::Value;
    public $refreshtoken = parent::Value;
    public $routingnumber = parent::Value;
    public $salt = parent::Value;
    public $secret = parent::Value;
    public $secretkey = parent::Value;
    public $secrettoken = parent::Value;
    public $securityanswer = parent::Value;
    public $securitycode = parent::Value;
    public $securityquestion = parent::Value;
    public $serviceaccountcredentials = parent::Value;
    public $session = parent::Value;
    public $sessionid = parent::Value;
    public $sessionkey = parent::Value;
    public $setcookie = parent::Value;
    public $signature = parent::Value;
    public $signaturekey = parent::Value;
    public $sshkey = parent::Value;
    public $ssn = parent::Value;
    public $symfony = parent::Value;
    public $token = parent::Value;
    public $transactionid = parent::Value;
    public $twiliotoken = parent::Value;
    public $usersession = parent::Value;
    public $voterid = parent::Value;
    public $xapikey = parent::Value;
    public $xauthtoken = parent::Value;
    public $xcsrftoken = parent::Value;
    public $xforwardedfor = parent::Value;
    public $xrealip = parent::Value;
    public $xsrf = parent::Value;
    public $xsrftoken = parent::Value;

    public $customidentifier1 = parent::Value;
    public $customidentifier2 = parent::Value;
}

class CustomPii extends PiiBase {
    public $customkey = parent::Value;
}
