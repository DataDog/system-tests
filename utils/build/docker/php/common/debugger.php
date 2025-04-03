<?php

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
        $this->intLocal = $intArg * strlen($arg);
        return "Span Decoration Probe " . $this->intLocal;
    }

    public function mixProbe($arg, $intArg) {
        $this->intMixLocal = $intArg * strlen($arg);
        return "Mixed result " . $this->intMixLocal;
    }

    public function pii() {
        // Simulating Pii class behavior
        $testValue = "test_value";
        $customTestValue = "custom_test_value";
        return "PII " . $testValue . ". CustomPII " . $customTestValue;
    }

    public function expression($inputValue) {
        $localValue = strlen($inputValue);
        return "Great success number " . $localValue;
    }

    public function ExpressionException() {
        http_response_code(500);
        return "Hello from exception";
    }

    public function ExpressionOperators($intValue, $floatValue, $strValue) {
        return "Int value " . $intValue . ". Float value " . $floatValue . ". String value is " . $strValue . ".";
    }

    public function StringOperations($strValue, $emptyString = "", $nullString = null) {
        return "strValue " . $strValue . ". emptyString " . $emptyString . ". " . $nullString . ".";
    }

    public function collectionOperations() {
        // Simulating collection operations with different PHP collection types
        $a0 = array();
        $l0 = new SplFixedArray(0);
        $h0 = array();
        $a1 = array(1);
        $l1 = new SplFixedArray(1);
        $l1[0] = 1;
        $h1 = array('key' => 1);
        $a5 = array(1, 2, 3, 4, 5);
        $l5 = new SplFixedArray(5);
        for ($i = 0; $i < 5; $i++) {
            $l5[$i] = $i + 1;
        }
        $h5 = array(
            'k1' => 1,
            'k2' => 2,
            'k3' => 3,
            'k4' => 4,
            'k5' => 5
        );

        $a0_count = count($a0);
        $l0_count = $l0->count();
        $h0_count = count($h0);
        $a1_count = count($a1);
        $l1_count = $l1->count();
        $h1_count = count($h1);
        $a5_count = count($a5);
        $l5_count = $l5->count();
        $h5_count = count($h5);

        return "{$a0_count},{$a1_count},{$a5_count},{$l0_count},{$l1_count},{$l5_count},{$h0_count},{$h1_count},{$h5_count}.";
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
            echo "Debugger initialized";
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
        case 'metric':
            echo $controller->MetricProbe(intval($parts[1]));
            break;
        case 'budgets':
            echo $controller->Budgets(intval($parts[1]));
            break;
        case 'expression':
            switch ($parts[1]) {
                case 'exception':
                    echo $controller->ExpressionException();
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
