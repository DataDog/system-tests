<?php

// Block until the sidecar has received the agent /info response and applied
// peer-tag keys and span kinds to the concentrator.  Used by system tests
// that require peer tags to be available before making stats-generating requests.
$ready = dd_trace_internal_fn('await_agent_info');
header('Content-Type: application/json');
echo json_encode(['ready' => $ready]);
