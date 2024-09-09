package get_version

import (
    "os"
    "fmt"
	"runtime/debug"
)

func main() {
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
