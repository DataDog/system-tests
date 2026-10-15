<?php

namespace App\Models;

use Illuminate\Foundation\Auth\User as Authenticatable;

class User extends Authenticatable
{
    protected $primaryKey = 'id';
    public $incrementing = false;
    protected $keyType = 'string';

    protected $fillable = ['id', 'username', 'name', 'password', 'email'];
    protected $hidden = ['password'];

    // The ddtrace appsec extension checks offsetExists('email') before offsetExists('username')
    // when determining usr.login. Returning false for 'email' forces it to use 'username' instead.
    public function offsetExists($offset): bool
    {
        if ($offset === 'email') {
            return false;
        }
        return parent::offsetExists($offset);
    }
}
