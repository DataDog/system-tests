<?php

header('content-type: application/json');
$version=phpversion("ddtrace");
echo '{"status": "ok", "library": {"language": "php", "version": "' . $version . '"}}';
