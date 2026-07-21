<?php

namespace App\Entity;

use App\Repository\UserRepository;
use Doctrine\ORM\Mapping as ORM;
use Symfony\Component\Security\Core\User\PasswordAuthenticatedUserInterface;
use Symfony\Component\Security\Core\User\UserInterface;

#[ORM\Entity(repositoryClass: UserRepository::class)]
#[ORM\Table(name: 'users')]
class User implements UserInterface, PasswordAuthenticatedUserInterface
{
    #[ORM\Id]
    #[ORM\Column(length: 255)]
    private string $id;

    #[ORM\Column(length: 255, unique: true)]
    private string $username;

    #[ORM\Column(length: 255)]
    private string $password;

    #[ORM\Column(length: 255, nullable: true)]
    private ?string $name;

    public function __construct(string $id, string $username, string $password, ?string $name = null)
    {
        $this->id       = $id;
        $this->username = $username;
        $this->password = $password;
        $this->name     = $name;
    }

    public function getId(): string
    {
        return $this->id;
    }

    public function getUsername(): string
    {
        return $this->username;
    }

    public function getUserIdentifier(): string
    {
        return $this->username;
    }

    public function getPassword(): string
    {
        return $this->password;
    }

    public function getName(): string
    {
        return $this->name ?? '';
    }

    public function getRoles(): array
    {
        return ['ROLE_USER'];
    }

    public function eraseCredentials(): void {}
}
