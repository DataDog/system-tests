<?php

$rootSpan = \DDTrace\root_span();
DDTrace\add_distributed_tag("usr.id", base64_encode("usr.id"));
$rootSpan->meta['usr.id'] = "usr.id";
$rootSpan->meta['usr.name'] = "usr.name";
$rootSpan->meta['usr.email'] = "usr.email";
$rootSpan->meta['usr.session_id'] = "usr.session_id";
$rootSpan->meta['usr.role'] = "usr.role";
$rootSpan->meta['usr.scope'] = "usr.scope";

?>
