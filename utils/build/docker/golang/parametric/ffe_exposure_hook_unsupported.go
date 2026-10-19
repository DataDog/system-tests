//go:build !dd_exposure_hook

package main

import of "github.com/open-feature/go-sdk/openfeature"

// Older SDKs still build. Tests require callback rows and fail when forced on them.
func exposureHookOptions(_ *[]map[string]any) []of.Option { return nil }
