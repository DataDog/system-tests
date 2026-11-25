//go:build dd_flag_selection

package main

import ddof "github.com/DataDog/dd-trace-go/v2/openfeature"

func ffeProviderConfig(selection *ffeFlagSelection) ddof.ProviderConfig {
	config := ddof.ProviderConfig{}
	if selection != nil {
		config.FlagSelection = &ddof.FlagSelection{Tags: selection.Tags, KeyPatterns: selection.KeyPatterns}
	}
	return config
}
