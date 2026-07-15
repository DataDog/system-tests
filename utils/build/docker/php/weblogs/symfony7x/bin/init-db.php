#!/usr/bin/env php
<?php

use App\Entity\User;
use Doctrine\DBAL\DriverManager;
use Doctrine\ORM\EntityManager;
use Doctrine\ORM\ORMSetup;
use Doctrine\ORM\Tools\SchemaTool;

require dirname(__DIR__) . '/vendor/autoload.php';

$dbPath = getenv('SYMFONY_DB_PATH') ?: '/tmp/symfony.db';

$config = ORMSetup::createAttributeMetadataConfiguration(
    paths: [dirname(__DIR__) . '/src/Entity'],
    isDevMode: false,
);

$connection = DriverManager::getConnection(['driver' => 'pdo_sqlite', 'path' => $dbPath]);
$em         = new EntityManager($connection, $config);

(new SchemaTool($em))->createSchema($em->getMetadataFactory()->getAllMetadata());

$seeds = [
    ['id' => 'social-security-id',                    'username' => 'test',     'password' => '1234'],
    ['id' => '591dc126-8431-4d0f-9509-b23318d3dce4', 'username' => 'testuuid', 'password' => '1234'],
];

foreach ($seeds as $seed) {
    if ($em->find(User::class, $seed['id']) === null) {
        $em->persist(new User($seed['id'], $seed['username'], password_hash($seed['password'], PASSWORD_BCRYPT), $seed['username']));
    }
}

$em->flush();

echo "Database initialized at $dbPath\n";
