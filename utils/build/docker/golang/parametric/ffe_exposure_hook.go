//go:build dd_exposure_hook

package main

import (
	"context"
	"errors"

	ddof "github.com/DataDog/dd-trace-go/v2/openfeature"
	of "github.com/open-feature/go-sdk/openfeature"
)

type rejectingAfterHook struct{ of.UnimplementedHook }

func (rejectingAfterHook) After(context.Context, of.HookContext, of.InterfaceEvaluationDetails, of.HookHints) error {
	return errors.New("application rejected the flag result")
}

func exposureHookOptions(rows *[]map[string]any, failAfter bool) []of.Option {
	hooks := make([]of.Hook, 0, 3)
	if failAfter {
		// After hooks run in reverse order. Reject after all exposure After hooks
		// would have run, to detect early emission and cache consumption.
		hooks = append(hooks, rejectingAfterHook{})
	}
	for id := range 2 {
		hooks = append(hooks, ddof.NewExposureHook(func(e ddof.ExposureEvaluation) {
			*rows = append(*rows, map[string]any{
				"hook": id, "flag": e.Details.FlagKey, "subject": e.Context.TargetingKey(),
				"variant": e.Details.Variant, "metadata": e.Details.FlagMetadata,
				"value": e.Details.Value, "errorCode": e.Details.ErrorCode, "reason": e.Details.Reason,
				"isExposure": e.IsExposure(), "isCacheHit": e.IsCacheHit(), "shouldSend": e.ShouldSend(),
				"features": e.Features(),
			})
		}))
	}
	return []of.Option{of.WithHooks(hooks...)}
}
