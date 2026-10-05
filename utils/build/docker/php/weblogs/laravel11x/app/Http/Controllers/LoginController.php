<?php

namespace App\Http\Controllers;

use App\Models\User;
use Illuminate\Auth\Events\Registered;
use Illuminate\Http\Request;
use Illuminate\Http\Response;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Hash;

class LoginController
{
    private static array $newUsers = [
        'testnew' => ['id' => 'new-user'],
    ];

    public function login(Request $request)
    {
        $auth = $request->query('auth', '');

        if ($auth === 'local') {
            return $this->handleLocalLogin($request);
        }

        if ($auth === 'basic') {
            return $this->handleBasicLogin($request);
        }

        return response('', 200);
    }

    public function signup(Request $request)
    {
        $username = $request->input('username', '');
        $password = $request->input('password', '');

        $user = User::create([
            'id' => $username === 'testnew' ? 'new-user' : Hash::make($username),
            'username' => $username,
            'password' => Hash::make($password),
            'name'     => $username,
        ]);

        event(new Registered($user));

        Auth::login($user);

        return response('', 200);
    }

    private function handleLocalLogin(Request $request)
    {
        if (!$request->isMethod('POST')) {
            return response('', 200);
        }

        $username   = $request->input('username', '');
        $password   = $request->input('password', '');
        $sdkEvent   = $request->query('sdk_event', '');
        $sdkTrigger = $request->query('sdk_trigger', '');
        $sdkUser    = $request->query('sdk_user', '');
        $sdkExists  = $request->boolean('sdk_user_exists');

        if ($sdkTrigger === 'before' && $sdkEvent !== '') {
            $this->callSdk($sdkEvent, $sdkUser, $sdkExists);
        }

        $success = Auth::attempt(['username' => $username, 'password' => $password]);

        if ($sdkTrigger === 'after' && $sdkEvent !== '') {
            $this->callSdk($sdkEvent, $sdkUser, $sdkExists);
        }

        if ($success) {
            $request->session()->regenerate();
            return response('', 200);
        }

        return response('', 401);
    }

    private function handleBasicLogin(Request $request)
    {
        $authHeader = $request->header('Authorization', '');
        if (!str_starts_with($authHeader, 'Basic ')) {
            return response('', 401);
        }

        $decoded  = base64_decode(substr($authHeader, 6));
        $parts    = explode(':', $decoded, 2);
        $username = $parts[0] ?? '';
        $password = $parts[1] ?? '';

        $sdkEvent   = $request->query('sdk_event', '');
        $sdkTrigger = $request->query('sdk_trigger', '');
        $sdkUser    = $request->query('sdk_user', '');
        $sdkExists  = $request->boolean('sdk_user_exists');

        if ($sdkTrigger === 'before' && $sdkEvent !== '') {
            $this->callSdk($sdkEvent, $sdkUser, $sdkExists);
        }

        $success = Auth::attempt(['username' => $username, 'password' => $password]);

        if ($sdkTrigger === 'after' && $sdkEvent !== '') {
            $this->callSdk($sdkEvent, $sdkUser, $sdkExists);
        }

        if ($success) {
            return response('', 200);
        }

        return response('', 401);
    }

    private function callSdk(string $event, string $user, bool $exists): void
    {
        if ($event === 'success') {
            \datadog\appsec\track_user_login_success_event($user, []);
        } else {
            \datadog\appsec\track_user_login_failure_event($user, $exists, []);
        }
    }
}
