<?php

$code = isset($_GET['code']) ? (int)$_GET['code'] : 200;
http_response_code($code);
echo "Stats unique response";
