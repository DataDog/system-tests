package dbm

import (
	"context"
	"database/sql"
	"database/sql/driver"
	"encoding/json"
	"net/http"
	"sync"

	sqltrace "github.com/DataDog/dd-trace-go/contrib/database/sql/v2"
	"github.com/lib/pq"
)

var (
	globalSpyDrv *spyDriver

	pgConnStr = "postgres://system_tests_user:system_tests@postgres:5433/system_tests_dbname?sslmode=disable"

	dbOnce sync.Once
	pgDB   *sql.DB
)

type spyDriver struct {
	real driver.Driver
	mu   sync.Mutex
	last string
}

func (d *spyDriver) Open(name string) (driver.Conn, error) {
	realConn, err := d.real.Open(name)
	if err != nil {
		return nil, err
	}
	return &spyConn{real: realConn, spy: d}, nil
}

type spyConn struct {
	real driver.Conn
	spy  *spyDriver
}

func (c *spyConn) Prepare(query string) (driver.Stmt, error) {
	c.spy.mu.Lock()
	c.spy.last = query
	c.spy.mu.Unlock()
	return c.real.Prepare(query)
}

func (c *spyConn) Close() error              { return c.real.Close() }
func (c *spyConn) Begin() (driver.Tx, error) { return c.real.Begin() }

func (c *spyConn) QueryContext(ctx context.Context, query string, args []driver.NamedValue) (driver.Rows, error) {
	c.spy.mu.Lock()
	c.spy.last = query
	c.spy.mu.Unlock()
	if qc, ok := c.real.(driver.QueryerContext); ok {
		return qc.QueryContext(ctx, query, args)
	}
	stmt, err := c.real.Prepare(query)
	if err != nil {
		return nil, err
	}
	defer stmt.Close()
	vals := make([]driver.Value, len(args))
	for i, a := range args {
		vals[i] = a.Value
	}
	return stmt.Query(vals)
}

func init() {
	globalSpyDrv = &spyDriver{real: &pq.Driver{}}
	sqltrace.Register("postgres", globalSpyDrv)
}

func getPgDB() *sql.DB {
	dbOnce.Do(func() {
		var err error
		pgDB, err = sqltrace.Open("postgres", pgConnStr)
		if err != nil {
			panic("dbm: failed to open spy postgres pool: " + err.Error())
		}
	})
	return pgDB
}

func StubDbmHandler(w http.ResponseWriter, r *http.Request) {
	integration := r.URL.Query().Get("integration")
	if integration != "pg" {
		http.Error(w, "unsupported integration: "+integration, http.StatusBadRequest)
		return
	}

	rows, err := getPgDB().QueryContext(r.Context(), "SELECT version()")
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	rows.Close()

	globalSpyDrv.mu.Lock()
	lastSQL := globalSpyDrv.last
	globalSpyDrv.mu.Unlock()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "ok", "dbm_comment": lastSQL})
}
