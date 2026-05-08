<?php

namespace App\Providers;

use App\Models\User;
use Illuminate\Contracts\Auth\Authenticatable;
use Illuminate\Contracts\Auth\UserProvider;

class ArrayUserProvider implements UserProvider
{
    private static array $users = [
        'test' => [
            'id'       => 'social-security-id',
            'username' => 'test',
            'password' => '1234',
            'email'    => 'testuser@ddog.com',
            'name'     => 'test',
        ],
        'testuuid' => [
            'id'       => '591dc126-8431-4d0f-9509-b23318d3dce4',
            'username' => 'testuuid',
            'password' => '1234',
            'email'    => 'testuseruuid@ddog.com',
            'name'     => 'testuuid',
        ],
    ];

    public static function addUser(string $username, string $id, string $email = ''): void
    {
        self::$users[$username] = [
            'id'       => $id,
            'username' => $username,
            'password' => '1234',
            'email'    => $email ?: ($username . '@ddog.com'),
            'name'     => $username,
        ];
    }

    public function retrieveById($identifier): ?Authenticatable
    {
        foreach (self::$users as $data) {
            if ($data['id'] === $identifier) {
                return new User([
                    'id'       => $data['id'],
                    'username' => $data['username'],
                    'password' => $data['password'],
                    'name'     => $data['name'],
                ]);
            }
        }
        return null;
    }

    public function retrieveByToken($identifier, $token): ?Authenticatable
    {
        return null;
    }

    public function updateRememberToken(Authenticatable $user, $token): void {}

    public function retrieveByCredentials(array $credentials): ?Authenticatable
    {
        $username = $credentials['username'] ?? null;
        if ($username !== null && isset(self::$users[$username])) {
            $data = self::$users[$username];
            return new User([
                'id'       => $data['id'],
                'username' => $data['username'],
                'password' => $data['password'],
                'name'     => $data['name'],
            ]);
        }
        return null;
    }

    public function validateCredentials(Authenticatable $user, array $credentials): bool
    {
        return ($credentials['password'] ?? '') === $user->getAuthPassword();
    }

    public function rehashPasswordIfRequired(Authenticatable $user, array $credentials, bool $force = false): void {}
}
