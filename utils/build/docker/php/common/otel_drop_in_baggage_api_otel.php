<?php

$url = $_GET['url'] ?? null;
$baggage_remove = $_GET['baggage_remove'] ?? null;
$baggage_set = $_GET['baggage_set'] ?? null;

if ($url === null) {
    http_response_code(400);
    echo json_encode(['error' => 'Specify the url to call in the query string']);
    exit;
}

// open-telemetry/context (a dependency of open-telemetry/api) requires PHP ^8.1,
// so use the OTel Baggage API on PHP 8.1+ and DDTrace's native API on PHP 8.0.
if (PHP_VERSION_ID >= 80100) {
    require_once __DIR__ . '/vendor/autoload.php';

    $baggage = \OpenTelemetry\API\Baggage\Baggage::getCurrent();
    $builder = $baggage->toBuilder();

    if ($baggage_remove !== null) {
        foreach (explode(',', $baggage_remove) as $key) {
            $builder = $builder->remove(trim($key));
        }
    }

    if ($baggage_set !== null) {
        foreach (explode(',', $baggage_set) as $item) {
            $parts = explode('=', $item, 2);
            if (count($parts) === 2) {
                $builder = $builder->set(trim($parts[0]), trim($parts[1]));
            }
        }
    }

    $scope = $builder->build()->activate();
} else {
    $scope = null;
    $span = \DDTrace\root_span();
    if ($span !== null) {
        if ($baggage_remove !== null) {
            foreach (explode(',', $baggage_remove) as $key) {
                unset($span->baggage[trim($key)]);
            }
        }
        if ($baggage_set !== null) {
            foreach (explode(',', $baggage_set) as $item) {
                $parts = explode('=', $item, 2);
                if (count($parts) === 2) {
                    $span->baggage[trim($parts[0])] = trim($parts[1]);
                }
            }
        }
    }
}

try {
    $ch = curl_init($url);

    $response_headers_array = [];

    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_HEADER, false);
    curl_setopt($ch, CURLINFO_HEADER_OUT, true);

    curl_setopt($ch, CURLOPT_HEADERFUNCTION, function($curl, $header) use (&$response_headers_array) {
        $len = strlen($header);
        $header = explode(':', $header, 2);
        if (count($header) < 2) {
            return $len;
        }
        $response_headers_array[strtolower(trim($header[0]))] = trim($header[1]);
        return $len;
    });

    $response_body = curl_exec($ch);
    $status_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);

    $request_headers_array = [];
    $request_headers_raw = curl_getinfo($ch, CURLINFO_HEADER_OUT);
    if ($request_headers_raw) {
        foreach (explode("\r\n", $request_headers_raw) as $line) {
            if (strpos($line, ':') !== false) {
                list($key, $value) = explode(':', $line, 2);
                $request_headers_array[trim($key)] = trim($value);
            }
        }
    }

    curl_close($ch);

    header('Content-Type: application/json');
    echo json_encode([
        'url' => $url,
        'status_code' => $status_code,
        'request_headers' => $request_headers_array,
        'response_headers' => $response_headers_array,
    ]);
} finally {
    if ($scope !== null) {
        $scope->detach();
    }
}
