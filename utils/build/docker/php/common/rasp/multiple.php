<?php
@file_get_contents(urldecode($_GET["file1"]));
@file_get_contents(urldecode($_GET["file2"]));
@file_get_contents('../etc/passwd');

echo "Hello, multiple rasp!";
