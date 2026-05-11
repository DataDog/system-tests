<?php

namespace Database\Seeders;

use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\DB;

class UserSeeder extends Seeder
{
    public function run(): void
    {
        DB::table('users')->insert([
            [
                'username' => 'test',
                'name'     => 'test',
                'password' => bcrypt('1234'),
            ],
            [
                'username' => 'testuuid',
                'name'     => 'testuuid',
                'password' => bcrypt('1234'),
            ],
        ]);
    }
}
