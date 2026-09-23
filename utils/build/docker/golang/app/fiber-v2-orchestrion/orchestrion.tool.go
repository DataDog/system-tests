//go:build tools

package tools

import (
	_ "github.com/DataDog/orchestrion"

	_ "github.com/DataDog/dd-trace-go/orchestrion/all/v2" // integration

	// Fiber uses the server flag added by the FastHTTP integration.
	// The v2.0.0 all bundle does not include this integration.
	_ "github.com/DataDog/dd-trace-go/contrib/valyala/fasthttp/v2" // integration
)
