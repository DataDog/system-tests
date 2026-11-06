<?php

namespace Database\Seeders;

use App\Models\User;
use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\Hash;

class UserSeeder extends Seeder
{
    /**
     * Seed users aligned with tests/appsec/test_automated_login_events.py (USER, UUID_USER, PASSWORD).
     */
    public function run(): void
    {
        User::updateOrCreate(
            ['username' => 'test'],
            [
                'id'       => 'social-security-id',
                'name'     => 'test',
                'password' => Hash::make('1234'),
                'email'    => 'testuser@ddog.com',
            ]
        );

        User::updateOrCreate(
            ['username' => 'testuuid'],
            [
                'id'       => '591dc126-8431-4d0f-9509-b23318d3dce4',
                'name'     => 'testuuid',
                'password' => Hash::make('1234'),
                'email'    => 'testuseruuid@ddog.com',
            ]
        );
    }
}
