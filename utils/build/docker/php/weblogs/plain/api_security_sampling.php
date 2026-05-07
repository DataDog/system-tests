<?php

$uri = $_SERVER['PATH_INFO'];
$uri = preg_replace('/\?.*/', '', $uri);
if (preg_match('@\A/api_security(.)sampling/(\d+)\z@', $uri, $matches)) {
    $rootSpan = \DDTrace\root_span();
    if ($matches[1] == '_') {
        $rootSpan->meta["http.route"] = '/api_security_sampling/{id}';
        $status = 200;
    } else {
        $rootSpan->meta["http.route"] = '/api_security/sampling/{status}';
        $status = intval($matches[2]);
    }
    if ($status >= 200 && $status <= 599) {
        http_response_code($status);
        header("Content-type: application/json");
        echo '{"status":', $status, "}\n";
        die;
    }
}

http_response_code(400);
header("Content-type: text/plain");
echo "Invalid URI: $uri\n";
