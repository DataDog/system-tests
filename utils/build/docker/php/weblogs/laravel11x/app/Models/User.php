<?php

namespace App\Models;

use Illuminate\Auth\Authenticatable as AuthenticatableTrait;
use Illuminate\Contracts\Auth\Authenticatable;

class User implements Authenticatable
{
    use AuthenticatableTrait;

    public function __construct(private array $attributes) {}

    public function __get(string $key): mixed
    {
        return $this->attributes[$key] ?? null;
    }

    public function __isset(string $key): bool
    {
        return isset($this->attributes[$key]);
    }

    public function getAuthIdentifierName(): string
    {
        return 'id';
    }

    public function getAuthIdentifier(): mixed
    {
        return $this->attributes['id'];
    }

    public function getAuthPasswordName(): string
    {
        return 'password';
    }

    public function getAuthPassword(): string
    {
        return $this->attributes['password'];
    }

    public static function create(array $attributes): self
    {
        $user = new self($attributes);
        event(new \Illuminate\Auth\Events\Registered($user));
        return $user;
    }
}
