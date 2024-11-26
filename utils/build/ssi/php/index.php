<?php

if ($_SERVER['REQUEST_URI'] == '/crashme') {
    preg_match("/(0)*/", str_repeat("0", 15000));
} else if ($_SERVER['REQUEST_URI'] == '/fork_and_crash') {
    $pid = pcntl_fork();
    if ($pid) {
        pcntl_wait($status);
    } else {
        preg_match("/(0)*/", str_repeat("0", 15000));
    }
}

echo 'hi';
