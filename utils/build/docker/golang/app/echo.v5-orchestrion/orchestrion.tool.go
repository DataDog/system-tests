//go:build tools

package tools

import (
	_ "github.com/DataDog/orchestrion"

	// The echo.v5 contrib must be referenced explicitly here so that go mod
	// tidy keeps it in this module's dependency graph. Otherwise it would be
	// dropped (no direct import in main.go — orchestrion injects the wrap
	// at compile time via the contrib's orchestrion.yml join-point) and
	// install_ddtrace.sh would not list it among $CONTRIBS to override.
	_ "github.com/DataDog/dd-trace-go/contrib/labstack/echo.v5/v2" // integration
	_ "github.com/DataDog/dd-trace-go/orchestrion/all/v2"          // integration
)
