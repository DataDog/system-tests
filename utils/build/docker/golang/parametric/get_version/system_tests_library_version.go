package main

import (
    "os"
    "fmt"
	"runtime/debug"
    "gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"
)

func main() {
	tracer.Start()
	defer tracer.Stop()
    moduleName := "gopkg.in/DataDog/dd-trace-go.v1"

    if bi, ok := debug.ReadBuildInfo(); ok {
        for _, mod := range bi.Deps {
            if mod.Path == moduleName {
                fmt.Printf(mod.Version)
                return
            }
        }
    }

    fmt.Printf("Module %s not found.\n", moduleName)
	os.Exit(1)
}
