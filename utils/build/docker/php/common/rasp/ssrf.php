<?php

$span = \DDTrace\active_span();
if ($span) {
    $span->meta['_dd.appsec.json'] = '
{
  "triggers": [
      {
        "rule": {
          "id": "rasp-934-100",
          "name": "Server-side request forgery exploit",
          "tags": {
            "type": "ssrf",
            "category": "vulnerability_trigger",
            "capec": "1000/225/115/664",
            "cwe": 918,
            "confidence": 0,
            "module": "rasp"
          },
          "on_match": [
            "stack_trace",
            "block"
          ]
        },
        "rule_matches": [
          {
            "operator": "ssrf_detector",
            "parameters": [
              {
                "resource": {
                  "address": "server.io.net.url",
                  "key_path": [],
                  "value": "http://169.254.169.254"
                },
                "params": {
                  "address": "server.request.query",
                  "key_path": [],
                  "value": "169.254.169.254"
                },
                "highlight": [
                  "169.254.169.254"
                ]
              }
            ]
          }
        ],
        "stack_id": "f523bfb9-56e0-4697-1b6c-12a5e4a1f72e"
      }
    ]
  }
';

    http_response_code(403);  
}

echo "Hello SSRF";

?>
