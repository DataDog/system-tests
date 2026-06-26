<?php

use App\Kernel;
use Symfony\Component\HttpFoundation\Request;

require dirname(__DIR__).'/vendor/autoload.php';

// Strip trailing slash from non-root paths so Symfony never generates a strict_slashes 301 redirect
$_uri = $_SERVER['REQUEST_URI'] ?? '/';
$_qpos = strpos($_uri, '?');
$_path = $_qpos !== false ? substr($_uri, 0, $_qpos) : $_uri;
if (strlen($_path) > 1 && substr($_path, -1) === '/') {
    $_SERVER['REQUEST_URI'] = rtrim($_path, '/') . ($_qpos !== false ? substr($_uri, $_qpos) : '');
}

$kernel = new Kernel($_SERVER['APP_ENV'] ?? 'prod', (bool) ($_SERVER['APP_DEBUG'] ?? false));
$request = Request::createFromGlobals();
$response = $kernel->handle($request);
$response->send();
$kernel->terminate($request, $response);
