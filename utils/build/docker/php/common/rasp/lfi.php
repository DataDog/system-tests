<?php

$span = \DDTrace\active_span();
if ($span) {
    $span->meta['_dd.appsec.json'] = '
{
  "triggers": [
      {
        "rule": {
          "id": "rasp-930-100",
          "name": "Local file inclusion exploit",
          "tags": {
            "type": "lfi",
            "category": "vulnerability_trigger",
            "capec": "1000/255/153/126",
            "cwe": 22,
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
            "operator": "lfi_detector",
            "parameters": [
              {
                "resource": {
                  "address": "server.io.fs.file",
                  "key_path": [],
                  "value": "../etc/passwd"
                },
                "params": {
                  "address": "server.request.query",
                  "key_path": [],
                  "value": "../etc/passwd"
                },
                "highlight": [
                  "../etc/passwd"
                ]
              }
            ]
          }
        ],
        "stack_id": "955b0658-651f-45c7-1b58-50b82e8a04b7"
      }
    ]
  }
';

    http_response_code(403);  
}


?>
