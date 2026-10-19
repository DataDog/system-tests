//go:build dd_exposure_hook

package main

import (
	ddof "github.com/DataDog/dd-trace-go/v2/openfeature"
	of "github.com/open-feature/go-sdk/openfeature"
)

func exposureHookOptions(rows *[]map[string]any) []of.Option {
	hooks := make([]of.Hook, 0, 2)
	for id := range 2 {
		hooks = append(hooks, ddof.NewExposureHook(func(e ddof.ExposureEvaluation) {
			*rows = append(*rows, map[string]any{
				"hook": id, "flag": e.Details.FlagKey, "subject": e.Context.TargetingKey(),
				"variant": e.Details.Variant, "metadata": e.Details.FlagMetadata,
				"isExposure": e.IsExposure(), "isCacheHit": e.IsCacheHit(), "shouldSend": e.ShouldSend(),
			})
		}))
	}
	return []of.Option{of.WithHooks(hooks...)}
}
