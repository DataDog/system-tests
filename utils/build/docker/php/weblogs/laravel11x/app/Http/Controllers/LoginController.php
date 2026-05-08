<?php

namespace App\Http\Controllers;

use App\Models\User;
use App\Providers\ArrayUserProvider;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;

class LoginController
{
    private static array $newUsers = [
        'testnew' => ['id' => 'new-user', 'email' => 'testnewuser@ddog.com'],
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
        $id       = self::$newUsers[$username]['id'] ?? '';
        $email    = self::$newUsers[$username]['email'] ?? ($username . '@ddog.com');

        ArrayUserProvider::addUser($username, $id, $email);

        $user = User::create([
            'id'       => $id,
            'username' => $username,
            'password' => '1234',
            'name'     => $username,
        ]);

        Auth::login($user);

        return response('', 200);
    }

    private function handleLocalLogin(Request $request)
    {
        if (!$request->isMethod('POST')) {
            return response('', 200);
        }

        $username = $request->input('username', '');
        $password = $request->input('password', '');

        if (Auth::attempt(['username' => $username, 'password' => $password])) {
            $request->session()->regenerate();
            $userId = Auth::id();
            return response('', 200)->cookie('user_logged_in', $userId);
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

        if (Auth::attempt(['username' => $username, 'password' => $password])) {
            $userId = Auth::id();
            return response('', 200)->cookie('user_logged_in', $userId);
        }

        return response('', 401);
    }
}
