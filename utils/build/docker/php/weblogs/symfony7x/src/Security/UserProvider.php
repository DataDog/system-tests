<?php

namespace App\Security;

use Symfony\Component\Security\Core\Exception\UserNotFoundException;
use Symfony\Component\Security\Core\User\UserInterface;
use Symfony\Component\Security\Core\User\UserProviderInterface;

class UserProvider implements UserProviderInterface
{
    private \PDO $pdo;

    public function __construct()
    {
        $dbPath = $_ENV['SYMFONY_DB_PATH'] ?? '/tmp/symfony.db';
        $this->pdo = new \PDO("sqlite:$dbPath");
    }

    public function loadUserByIdentifier(string $identifier): UserInterface
    {
        $stmt = $this->pdo->prepare('SELECT * FROM users WHERE username = ?');
        $stmt->execute([$identifier]);
        $row = $stmt->fetch(\PDO::FETCH_ASSOC);

        if (!$row) {
            throw new UserNotFoundException(sprintf('User "%s" not found.', $identifier));
        }

        return User::fromDbRow($row);
    }

    public function refreshUser(UserInterface $user): UserInterface
    {
        return $this->loadUserByIdentifier($user->getUserIdentifier());
    }

    public function supportsClass(string $class): bool
    {
        return $class === User::class || is_subclass_of($class, User::class);
    }
}
