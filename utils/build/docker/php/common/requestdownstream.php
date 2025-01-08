<?php

$ch = curl_init("http://127.0.0.1:7777/returnheaders");

curl_exec($ch);
if(curl_error($ch)) {
    fwrite($fp, curl_error($ch));
}
curl_close($ch);
