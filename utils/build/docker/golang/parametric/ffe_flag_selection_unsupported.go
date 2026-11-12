//go:build !dd_flag_selection

package main

import ddof "github.com/DataDog/dd-trace-go/v2/openfeature"

// Older SDKs still build. Flag selection tests fail when forced on them.
func ffeProviderConfig(_ *ffeFlagSelection) ddof.ProviderConfig { return ddof.ProviderConfig{} }
