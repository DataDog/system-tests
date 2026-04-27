<?php

class Pii {
    public $_2fa                        = "SHOULD_BE_REDACTED";
    public $ACCESSTOKEN                 = "SHOULD_BE_REDACTED";
    public $Access_Token                = "SHOULD_BE_REDACTED";
    public $AccessToken                 = "SHOULD_BE_REDACTED";
    public $accessToken                 = "SHOULD_BE_REDACTED";
    public $access_token                = "SHOULD_BE_REDACTED";
    public $accesstoken                 = "SHOULD_BE_REDACTED";
    public $aiohttpsession              = "SHOULD_BE_REDACTED";
    public $apikey                      = "SHOULD_BE_REDACTED";
    public $apisecret                   = "SHOULD_BE_REDACTED";
    public $apisignature                = "SHOULD_BE_REDACTED";
    public $appkey                      = "SHOULD_BE_REDACTED";
    public $applicationkey              = "SHOULD_BE_REDACTED";
    public $auth                        = "SHOULD_BE_REDACTED";
    public $authorization               = "SHOULD_BE_REDACTED";
    public $authtoken                   = "SHOULD_BE_REDACTED";
    public $ccnumber                    = "SHOULD_BE_REDACTED";
    public $certificatepin              = "SHOULD_BE_REDACTED";
    public $cipher                      = "SHOULD_BE_REDACTED";
    public $clientid                    = "SHOULD_BE_REDACTED";
    public $clientsecret                = "SHOULD_BE_REDACTED";
    public $connectionstring            = "SHOULD_BE_REDACTED";
    public $connectsid                  = "SHOULD_BE_REDACTED";
    public $cookie                      = "SHOULD_BE_REDACTED";
    public $credentials                 = "SHOULD_BE_REDACTED";
    public $creditcard                  = "SHOULD_BE_REDACTED";
    public $csrf                        = "SHOULD_BE_REDACTED";
    public $csrftoken                   = "SHOULD_BE_REDACTED";
    public $cvv                         = "SHOULD_BE_REDACTED";
    public $databaseurl                 = "SHOULD_BE_REDACTED";
    public $dburl                       = "SHOULD_BE_REDACTED";
    public $encryptionkey               = "SHOULD_BE_REDACTED";
    public $encryptionkeyid             = "SHOULD_BE_REDACTED";
    public $geolocation                 = "SHOULD_BE_REDACTED";
    public $gpgkey                      = "SHOULD_BE_REDACTED";
    public $ipaddress                   = "SHOULD_BE_REDACTED";
    public $jti                         = "SHOULD_BE_REDACTED";
    public $jwt                         = "SHOULD_BE_REDACTED";
    public $licensekey                  = "SHOULD_BE_REDACTED";
    public $masterkey                   = "SHOULD_BE_REDACTED";
    public $mysqlpwd                    = "SHOULD_BE_REDACTED";
    public $nonce                       = "SHOULD_BE_REDACTED";
    public $oauth                       = "SHOULD_BE_REDACTED";
    public $oauthtoken                  = "SHOULD_BE_REDACTED";
    public $otp                         = "SHOULD_BE_REDACTED";
    public $passhash                    = "SHOULD_BE_REDACTED";
    public $passwd                      = "SHOULD_BE_REDACTED";
    public $password                    = "SHOULD_BE_REDACTED";
    public $passwordb                   = "SHOULD_BE_REDACTED";
    public $pemfile                     = "SHOULD_BE_REDACTED";
    public $pgpkey                      = "SHOULD_BE_REDACTED";
    public $phpsessid                   = "SHOULD_BE_REDACTED";
    public $pin                         = "SHOULD_BE_REDACTED";
    public $pincode                     = "SHOULD_BE_REDACTED";
    public $pkcs8                       = "SHOULD_BE_REDACTED";
    public $privatekey                  = "SHOULD_BE_REDACTED";
    public $publickey                   = "SHOULD_BE_REDACTED";
    public $pwd                         = "SHOULD_BE_REDACTED";
    public $recaptchakey                = "SHOULD_BE_REDACTED";
    public $refreshtoken                = "SHOULD_BE_REDACTED";
    public $routingnumber               = "SHOULD_BE_REDACTED";
    public $salt                        = "SHOULD_BE_REDACTED";
    public $secret                      = "SHOULD_BE_REDACTED";
    public $secretkey                   = "SHOULD_BE_REDACTED";
    public $secrettoken                 = "SHOULD_BE_REDACTED";
    public $securityanswer              = "SHOULD_BE_REDACTED";
    public $securitycode                = "SHOULD_BE_REDACTED";
    public $securityquestion            = "SHOULD_BE_REDACTED";
    public $serviceaccountcredentials   = "SHOULD_BE_REDACTED";
    public $session                     = "SHOULD_BE_REDACTED";
    public $sessionid                   = "SHOULD_BE_REDACTED";
    public $sessionkey                  = "SHOULD_BE_REDACTED";
    public $setcookie                   = "SHOULD_BE_REDACTED";
    public $signature                   = "SHOULD_BE_REDACTED";
    public $signaturekey                = "SHOULD_BE_REDACTED";
    public $sshkey                      = "SHOULD_BE_REDACTED";
    public $ssn                         = "SHOULD_BE_REDACTED";
    public $symfony                     = "SHOULD_BE_REDACTED";
    public $token                       = "SHOULD_BE_REDACTED";
    public $transactionid               = "SHOULD_BE_REDACTED";
    public $twiliotoken                 = "SHOULD_BE_REDACTED";
    public $usersession                 = "SHOULD_BE_REDACTED";
    public $voterid                     = "SHOULD_BE_REDACTED";
    public $xapikey                     = "SHOULD_BE_REDACTED";
    public $xauthtoken                  = "SHOULD_BE_REDACTED";
    public $xcsrftoken                  = "SHOULD_BE_REDACTED";
    public $xforwardedfor               = "SHOULD_BE_REDACTED";
    public $xrealip                     = "SHOULD_BE_REDACTED";
    public $xsrf                        = "SHOULD_BE_REDACTED";
    public $xsrftoken                   = "SHOULD_BE_REDACTED";
    public $customidentifier1           = "SHOULD_BE_REDACTED";
    public $customidentifier2           = "SHOULD_BE_REDACTED";
}

class CustomPii {
    public $customkey = "SHOULD_BE_REDACTED";
}

// Exception replay helper classes
class ExceptionReplayRock extends \RuntimeException {
    public function __construct() { parent::__construct("rock exception"); }
}
class ExceptionReplayPaper extends \RuntimeException {
    public function __construct() { parent::__construct("paper exception"); }
}
class ExceptionReplayScissors extends \RuntimeException {
    public function __construct() { parent::__construct("scissors exception"); }
}

class DebuggerController {
    private $intLocal = 0;
    private $intMixLocal = 0;

    public function LogProbe() {
        return "Log probe";
    }

    public function MetricProbe($id) {
        $id++;
        return "Metric Probe " . $id;
    }

    public function SpanProbe() {
        return "Span probe";
    }

    public function SpanDecorationProbe($arg, $intArg) {
        $intLocal = $intArg * strlen($arg);
        $this->intLocal = $intLocal;
        return "Span Decoration Probe " . $intLocal;
    }

    public function mixProbe($arg, $intArg) {
        $this->intMixLocal = $intArg * strlen($arg);
        return "Mixed result " . $this->intMixLocal;
    }

    public function pii() {
        $pii = new Pii();
        $customPii = new CustomPii();
        return "PII: " . $pii->password . " CustomPII: " . $customPii->customkey;
    }

    // ── Exception Replay endpoints ──────────────────────────────────────────

    public function exceptionReplaySimple() {
        throw new \RuntimeException("simple exception");
    }

    public function exceptionReplayRecursion(int $depth, int $originalDepth) {
        if ($depth <= 0) {
            throw new \RuntimeException("recursion exception depth $originalDepth");
        }
        $this->exceptionReplayRecursionHelper($depth - 1, $originalDepth);
        // unreachable, but satisfies never return type checker
    }

    private function exceptionReplayRecursionHelper(int $depth, int $originalDepth) {
        if ($depth <= 0) {
            throw new \RuntimeException("recursion exception depth $originalDepth");
        }
        $this->exceptionReplayRecursionHelper($depth - 1, $originalDepth);
    }

    public function exceptionReplayInner() {
        try {
            throw new \RuntimeException("inner exception");
        } catch (\RuntimeException $inner) {
            throw new \RuntimeException("outer exception", 0, $inner);
        }
    }

    public function exceptionReplayRps(string $shape): string {
        switch ($shape) {
            case 'rock':
                throw new ExceptionReplayRock();
            case 'paper':
                throw new ExceptionReplayPaper();
            case 'scissors':
                throw new ExceptionReplayScissors();
        }
        return "No exception";
    }

    private function exceptionReplayDeepA() {
        $this->exceptionReplayDeepB();
    }

    private function exceptionReplayDeepB() {
        $this->exceptionReplayDeepC();
    }

    private function exceptionReplayDeepC() {
        throw new \RuntimeException("multiple stack frames exception");
    }

    public function exceptionReplayMultiframe() {
        $this->exceptionReplayDeepA();
    }

    public function exceptionReplayAsync() {
        // PHP has no native async; simulate by throwing directly
        throw new \RuntimeException("async exception");
    }

    public function expression($inputValue) {
        $localValue = strlen($inputValue);
        $testStruct = (object)[
            'IntValue'    => 1,
            'DoubleValue' => 1.1,
            'StringValue' => "one",
            'BoolValue'   => true,
            'Collection'  => ["one", "two", "three"],
            'Dictionary'  => ["one" => 1, "two" => 2, "three" => 3, "four" => 4],
        ];
        return "Great success number " . $localValue;
    }

    public function ExpressionException() {
        throw new \RuntimeException("Hello from exception");
    }

    public function ExpressionOperators($intValue, $floatValue, $strValue) {
        $pii = new Pii();
        return "Int value " . $intValue . ". Float value " . $floatValue . ". String value is " . $strValue . ". Pii is " . get_class($pii) . ".";
    }

    public function StringOperations($strValue, $emptyString = "", $nullString = null) {
        return "strValue " . $strValue . ". emptyString " . $emptyString . ". " . $nullString . ".";
    }

    public function collectionOperations() {
        $l0 = new SplFixedArray(0);
        $l1 = new SplFixedArray(1);
        $l1[0] = 1;
        $l5 = new SplFixedArray(5);
        for ($i = 0; $i < 5; $i++) {
            $l5[$i] = $i;
        }
        // Use extract() to create array variables in the symbol table at runtime.
        // PHP constant-folds count(literal_array) and eliminates array CVs as dead
        // stores regardless of PHP version. extract() bypasses the CV mechanism
        // entirely — variables land in the symbol table, which is never pre-emptively
        // stripped by the compiler.
        extract([
            'a0' => [],
            'h0' => [],
            'a1' => [1],
            'h1' => [0 => 1],
            'a5' => [0, 1, 2, 3, 4],
            'h5' => [0 => 0, 1 => 1, 2 => 2, 3 => 3, 4 => 4],
        ]);

        return count($a0) . "," . count($a1) . "," . count($a5) . ","
             . $l0->count() . "," . $l1->count() . "," . $l5->count() . ","
             . count($h0) . "," . count($h1) . "," . count($h5) . ".";
    }

    public function nulls($intValue, $strValue, $boolValue) {
        $pii = $boolValue ? new stdClass() : null;
        return "Pii is null " . ($pii === null ? "true" : "false") . ". intValue is null " . ($intValue === null ? "true" : "false") . ". strValue is null " . ($strValue === null ? "true" : "false") . ".";
    }

    public function Budgets($loops) {
        for ($i = 0; $i < $loops; $i++) {
            // Empty loop to simulate the Python version
        }
        return "Budgets";
    }
}

// Request handling
$controller = new DebuggerController();
$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$parts = explode('/', trim($path, '/'));

// Remove the 'debugger' prefix if it exists
if (count($parts) > 0 && $parts[0] === 'debugger') {
    array_shift($parts);
}

$query = parse_url($_SERVER['REQUEST_URI'], PHP_URL_QUERY);
parse_str($query, $queryParams);

if (count($parts) === 1) {
    switch ($parts[0]) {
        case 'init':
            // If 'probes' query param is provided (comma-separated probe IDs), loop until
            // all requested probe IDs appear in the loaded remote config, then return.
            // Without 'probes', just trigger RC processing and return immediately.
            $expectedProbes = isset($queryParams['probes']) && $queryParams['probes'] !== ''
                ? explode(',', $queryParams['probes'])
                : [];
            $timeoutMs = isset($queryParams['timeout']) ? (int)$queryParams['timeout'] : 5000;
            $deadline = microtime(true) * 1000 + $timeoutMs;

            do {
                $loadedConfigs = dd_trace_internal_fn('get_loaded_remote_configs') ?: [];
                $loadedKeys = array_keys($loadedConfigs);

                $missing = [];
                foreach ($expectedProbes as $probeId) {
                    $found = false;
                    foreach ($loadedKeys as $configId) {
                        if (strpos($configId, $probeId) !== false) {
                            $found = true;
                            break;
                        }
                    }
                    if (!$found) {
                        $missing[] = $probeId;
                    }
                }

                if (empty($missing)) {
                    break;
                }

                usleep(10000); // 10ms between polls
            } while (microtime(true) * 1000 < $deadline);

            header('Content-Type: application/json');
            echo json_encode($loadedConfigs);
            break;
        case 'log':
            echo $controller->LogProbe();
            break;
        case 'span':
            echo $controller->SpanProbe();
            break;
        case 'pii':
            echo $controller->pii();
            break;
        case 'expression':
            if (!isset($queryParams['inputValue'])) {
                http_response_code(400);
                break;
            }
            echo $controller->expression($queryParams['inputValue']);
            break;
        default:
            http_response_code(404);
            break;
    }
} elseif (count($parts) === 2) {
    switch ($parts[0]) {
        case 'exceptionreplay':
            // http_response_code(500) must be called INSIDE the catch block with a bound variable
            // so that ddtrace's http_response_code hook can find the exception via the catch variable $e.
            try {
                switch ($parts[1]) {
                    case 'simple':
                        $controller->exceptionReplaySimple();
                        break;
                    case 'recursion':
                        $depth = isset($queryParams['depth']) ? intval($queryParams['depth']) : 3;
                        $controller->exceptionReplayRecursion($depth, $depth);
                        break;
                    case 'recursion_inline':
                        $depth = isset($queryParams['depth']) ? intval($queryParams['depth']) : 4;
                        $controller->exceptionReplayRecursion($depth, $depth);
                        break;
                    case 'inner':
                        $controller->exceptionReplayInner();
                        break;
                    case 'rps':
                        $shape = isset($queryParams['shape']) ? $queryParams['shape'] : 'rock';
                        $controller->exceptionReplayRps($shape);
                        break;
                    case 'multiframe':
                        $controller->exceptionReplayMultiframe();
                        break;
                    case 'async':
                        $controller->exceptionReplayAsync();
                        break;
                    default:
                        http_response_code(404);
                        break;
                }
            } catch (\Throwable $e) {
                http_response_code(500);
                echo $e->getMessage();
            }
            break;
        case 'metric':
            echo $controller->MetricProbe(intval($parts[1]));
            break;
        case 'budgets':
            echo $controller->Budgets(intval($parts[1]));
            break;
        case 'expression':
            switch ($parts[1]) {
                case 'exception':
                    try {
                        echo $controller->ExpressionException();
                    } catch (\Throwable $e) {
                        http_response_code(500);
                        echo $e->getMessage();
                    }
                    break;
                case 'operators':
                    $intValue = isset($queryParams['intValue']) ? intval($queryParams['intValue']) : null;
                    $floatValue = isset($queryParams['floatValue']) ? floatval($queryParams['floatValue']) : null;
                    $strValue = isset($queryParams['strValue']) ? $queryParams['strValue'] : null;
                    echo $controller->ExpressionOperators($intValue, $floatValue, $strValue);
                    break;
                case 'strings':
                    $strValue = isset($queryParams['strValue']) ? $queryParams['strValue'] : null;
                    $emptyString = isset($queryParams['emptyString']) ? $queryParams['emptyString'] : "";
                    $nullString = isset($queryParams['nullString']) ? $queryParams['nullString'] : null;
                    echo $controller->StringOperations($strValue, $emptyString, $nullString);
                    break;
                case 'collections':
                    echo $controller->collectionOperations();
                    break;
                case 'null':
                    $intValue = isset($queryParams['intValue']) ? intval($queryParams['intValue']) : null;
                    $strValue = isset($queryParams['strValue']) ? $queryParams['strValue'] : null;
                    $boolValue = isset($queryParams['boolValue']) ? filter_var($queryParams['boolValue'], FILTER_VALIDATE_BOOLEAN) : null;
                    echo $controller->nulls($intValue, $strValue, $boolValue);
                    break;
                default:
                    http_response_code(404);
                    break;
            }
            break;
        default:
            http_response_code(404);
            break;
    }
} elseif (count($parts) === 3) {
    switch ($parts[0]) {
        case 'span-decoration':
            echo $controller->SpanDecorationProbe($parts[1], intval($parts[2]));
            break;
        case 'mix':
            echo $controller->mixProbe($parts[1], intval($parts[2]));
            break;
        default:
            http_response_code(404);
            break;
    }
} else {
    http_response_code(404);
}
