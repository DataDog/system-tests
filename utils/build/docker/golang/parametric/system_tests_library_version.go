package getversion

import (
    "os"
    "fmt"
	"runtime/debug"
)


func main() {
    moduleName := "gopkg.in/DataDog/dd-trace-go.v1"

    // Obtenir les informations de build (dont les versions des modules)
    buildInfo, ok := debug.ReadBuildInfo()
    if !ok {
        fmt.Println("Can't read build informations.\n")
		os.Exit(1)
    }

    for _, mod := range buildInfo.Deps {
        if mod.Path == moduleName {
            fmt.Printf(mod.Version)
            return
        }
    }

    fmt.Printf("Module %s not found.\n", moduleName)
	os.Exit(1)
}
