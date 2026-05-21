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
    ],
];
