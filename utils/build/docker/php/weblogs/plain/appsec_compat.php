<?php

/**
 * Detect whether the installed appsec extension registers the _automated
 * functions under the internal sub-namespace (dd-trace-php >= 1.20).
 */
function _dd_appsec_new_api(): bool
{
    return function_exists('\datadog\appsec\internal\track_user_login_success_event_automated');
}
