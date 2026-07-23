//go:build tools

package tools

import (
	_ "github.com/DataDog/orchestrion"

	_ "github.com/DataDog/dd-iast-go"                     // integration
	_ "github.com/DataDog/dd-trace-go/orchestrion/all/v2" // integration
)
