<?php

use App\Http\Controllers\LoginController;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Route;

Route::get('/', function (Request $request) {
    Auth::user(); // trigger authenticated user tracking for logged-in sessions
    return response('Hello World!', 200)->header('Content-Type', 'text/plain');
});

Route::get('/healthcheck', function () {
    $version = phpversion('ddtrace') ?: 'unknown';
    return response()->json([
        'status'  => 'ok',
        'library' => ['name' => 'php', 'version' => $version],
    ]);
});

Route::get('/status', function (Request $request) {
    $code = intval($request->query('code', 200));
    return response('', $code);
});

Route::match(['GET', 'POST'], '/login', [LoginController::class, 'login']);

Route::post('/signup', [LoginController::class, 'signup']);
