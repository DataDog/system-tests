<?php

function setLoggedInCookie($username) {
    setcookie('user_logged_in', $username);
}

function getLoggedInCookie() {
    return $_COOKIE['user_logged_in'];
}
