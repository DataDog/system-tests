<?php

$span = \DDTrace\active_span();
if ($span) {
    $span->meta['_dd.appsec.json'] = '
{
  "triggers": [
      {
        "rule": {
          "id": "rasp-942-100",
          "name": "SQL injection exploit",
          "tags": {
            "type": "sql_injection",
            "category": "vulnerability_trigger",
            "capec": "1000/152/248/66",
            "cwe": 89,
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
            "operator": "sqli_detector",
            "operator_value": "",
            "parameters": [
              {
                "resource": {
                  "address": "server.db.statement",
                  "key_path": [],
                  "value": "SELECT * FROM table WHERE ? OR ? = ? --;"
                },
                "params": {
                  "address": "server.request.query",
                  "key_path": [],
                  "value": "\' OR 1 = 1 --"
                },
                "db_type": {
                  "address": "server.db.system",
                  "key_path": [],
                  "value": "mysql"
                },
                "highlight": [
                  "\' OR 1 = 1 --"
                ]
              }
            ]
          }
        ],
        "stack_id": "edbf5184-7047-401d-1b4f-531e29e92477"
      }
    ]
  }
';

    http_response_code(403);  
}

echo "Hello SSRF";

?>
