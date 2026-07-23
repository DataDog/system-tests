package main

import (
	"fmt"
	"net/http"
	"runtime"
	"time"
)

// The `debugger` feature allows attachment to specific lines of code.
// Due to differences in line numbering between libraries,
// 'dummy lines' are used to standardize this functionality.
// Dummy line

type DebuggerController struct{}

// Dummy line
func (d *DebuggerController) logProbe(w http.ResponseWriter, r *http.Request) {
	// Dummy line
	w.Write([]byte("Log probe"))
}

// Dummy line
// Dummy line
func (d *DebuggerController) mixProbe(w http.ResponseWriter, r *http.Request) {
	w.Write([]byte("Mix probe"))
}

// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
func (d *DebuggerController) expression(w http.ResponseWriter, r *http.Request) {
	inputValue := r.URL.Query().Get("inputValue")
	localValue := intLen(inputValue)
	testStruct := newExpressionTestStruct()
	expressionWrite(w, localValue, testStruct, inputValue)
	runtime.KeepAlive(testStruct)
}

type ExpressionTestStruct struct {
	IntValue    int
	DoubleValue float64
	StringValue string
	BoolValue   bool
	Collection  []string
	Dictionary  map[string]int
}

func newExpressionTestStruct() ExpressionTestStruct {
	return ExpressionTestStruct{
		IntValue:    1,
		DoubleValue: 1.1,
		StringValue: "one",
		BoolValue:   true,
		Collection:  []string{"one", "two", "three"},
		Dictionary:  map[string]int{"one": 1, "two": 2, "three": 3, "four": 4},
	}
}

//go:noinline
func intLen(s string) int {
	return len(s)
}

//go:noinline
func expressionWrite(w http.ResponseWriter, localValue int, testStruct ExpressionTestStruct, inputValue string) {
	w.Write([]byte(fmt.Sprintf("Great success number %d %s %s", localValue, testStruct.StringValue, inputValue)))
}

//go:noinline
func (d *DebuggerController) budgets(w http.ResponseWriter, r *http.Request, loops int) {
	total := 0
	for i := 0; i < loops; i++ {
		total += d.budgetStep(i, loops)
	}
	runtime.KeepAlive(total)
	w.Write([]byte("Budgets"))
}

//go:noinline
func (d *DebuggerController) budgetStep(i, loops int) int {
	return i + loops // loops is referenced so the capture-expression probe can read it at this line.
}

//go:noinline
func (d *DebuggerController) correlation(w http.ResponseWriter, r *http.Request) {
	result := d.correlationMiddle()
	time.Sleep(400 * time.Millisecond) // space the probed call sites in time
	runtime.KeepAlive(result)
	w.Write([]byte(fmt.Sprintf("Correlation %d", result)))
}

//go:noinline
func (d *DebuggerController) correlationMiddle() int {
	result := d.correlationLeaf()
	time.Sleep(400 * time.Millisecond) // space the probed call sites in time
	return result
}

//go:noinline
func (d *DebuggerController) correlationLeaf() int {
	return 3
}

//go:noinline
func (d *DebuggerController) correlationLoop(w http.ResponseWriter, r *http.Request, loops int) {
	total := 0
	for i := 0; i < loops; i++ {
		total += i // correlation loop body line probe
		time.Sleep(time.Second)
	}
	afterLoop := total // correlation loop sibling line probe
	runtime.KeepAlive(afterLoop)
	w.Write([]byte(fmt.Sprintf("Loop %d", afterLoop)))
}
