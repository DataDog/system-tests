<?php

ini_set("datadog.trace.hook_limit", "0");

$last_id = \DDtrace\install_hook("_dummy", function () {});
for ($i = 0; $i < 6000; ++$i) {
    usleep(1000);

    $id = \DDtrace\install_hook("_dummy", function () {});
    if ($last_id + 1 != $id) {
        break;
    }
    $last_id = $id;
}

$skipExecution = true;
include "debugger.php";
