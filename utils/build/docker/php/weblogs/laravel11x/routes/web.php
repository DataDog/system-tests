<?php

use Illuminate\Support\Facades\Route;

Route::get('/', function () {
    return response('Hello World!', 200)->header('Content-Type', 'text/plain');
});

Route::get('/healthcheck', function () {
    $version = phpversion('ddtrace') ?: 'unknown';
    return response()->json([
        'status' => 'ok',
        'library' => ['name' => 'php', 'version' => $version],
    ]);
});
