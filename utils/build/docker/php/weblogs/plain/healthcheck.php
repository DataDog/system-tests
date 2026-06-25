<?php

header('content-type: application/json');
$version=phpversion("ddtrace");
echo '{"status": "ok", "library": {"name": "php", "version": "' . $version . '"}}';
