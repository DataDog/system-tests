<?php

return [
    'default' => 'sqlite',
    'connections' => [
        'sqlite' => [
            'driver'   => 'sqlite',
            'database' => '/tmp/laravel.db',
            'prefix'   => '',
            'foreign_key_constraints' => false,
        ],
        'mysql' => [
            'driver'   => 'mysql',
            'host'     => 'mysqldb',
            'database' => 'mysql_dbname',
            'username' => 'mysqldb',
            'password' => 'mysqldb',
            'charset'  => 'utf8mb4',
            'collation' => 'utf8mb4_unicode_ci',
            'prefix'   => '',
            'strict'   => true,
        ],
        'postgresql' => [
            'driver'   => 'pgsql',
            'host'     => 'postgres',
            'port'     => 5433,
            'database' => 'system_tests_dbname',
            'username' => 'system_tests_user',
            'password' => 'system_tests',
            'charset'  => 'utf8',
            'prefix'   => '',
            'schema'   => 'public',
        ],
    ],
];
