#!/usr/bin/env php
<?php

use App\Entity\User;
use App\Kernel;
use Doctrine\ORM\Tools\SchemaTool;

require dirname(__DIR__).'/vendor/autoload.php';

$_SERVER['APP_ENV'] ??= 'prod';
$_SERVER['APP_DEBUG'] ??= false;

$kernel = new Kernel($_SERVER['APP_ENV'], (bool) $_SERVER['APP_DEBUG']);
$kernel->boot();

/** @var \Doctrine\ORM\EntityManagerInterface $em */
$em       = $kernel->getContainer()->get('doctrine.orm.entity_manager');
$metadata = $em->getMetadataFactory()->getAllMetadata();

$schemaTool = new SchemaTool($em);
$schemaTool->updateSchema($metadata, true);

$repo  = $em->getRepository(User::class);
$seeds = [
    ['id' => 'social-security-id',                    'username' => 'test',     'password' => '1234'],
    ['id' => '591dc126-8431-4d0f-9509-b23318d3dce4', 'username' => 'testuuid', 'password' => '1234'],
];

foreach ($seeds as $seed) {
    if ($repo->find($seed['id']) === null) {
        $em->persist(new User($seed['id'], $seed['username'], password_hash($seed['password'], PASSWORD_BCRYPT), $seed['username']));
    }
}

$em->flush();
$kernel->shutdown();

echo "Database initialized at " . ($_SERVER['SYMFONY_DB_PATH'] ?? '/tmp/symfony.db') . "\n";
