<?php

$url = $_GET["url"];

$ch = curl_init($url);
curl_exec($ch);
curl_close($ch);

echo "Ok";
