package rasp

import (
	"encoding/json"
	"encoding/xml"
	"errors"
	"log"
	"net/http"
	"os"

	sqltrace "github.com/DataDog/dd-trace-go/contrib/database/sql/v2"
	httptrace "github.com/DataDog/dd-trace-go/contrib/net/http/v2"
	"github.com/DataDog/dd-trace-go/v2/appsec"
	"github.com/DataDog/dd-trace-go/v2/appsec/events"

	_ "github.com/mattn/go-sqlite3" // To register the driver
)

func parseRASPRequest(r *http.Request, key string) string {
	var input string

	switch r.Method {
	case http.MethodGet:
		input = r.URL.Query().Get(key)
	case http.MethodPost:
		var (
			err  error
			body map[string]string
		)
		switch r.Header.Get("Content-Type") {
		case "application/json":
			err = json.NewDecoder(r.Body).Decode(&body)
		case "application/xml":
			var xmlBody []string
			xml.NewDecoder(r.Body).Decode(&xmlBody)
			body = map[string]string{key: xmlBody[0]}
		case "application/x-www-form-urlencoded":
			err = r.ParseForm()
			body = map[string]string{key: r.Form.Get(key)}
		default:
			err = errors.New("unsupported content type")
		}
		if err != nil {
			log.Fatalf("failed to parse body: %v\n", err)
		}

		if _, ok := body[key]; !ok {
			log.Fatalln("missing key in body: ", key)
		}

		if err := appsec.MonitorParsedHTTPBody(r.Context(), body); err != nil {
			log.Fatalf("Body Monitoring should not block the request: %v\n", err)
		}
		input = body[key]
	default:
		log.Fatalln("method not allowed")
	}

	if len(input) == 0 {
		log.Fatalln("missing required parameter")
	}

	return input
}

func LFI(w http.ResponseWriter, r *http.Request) {
	path := parseRASPRequest(r, "file")
	if path == "" {
		return
	}

	_, err := os.ReadFile(path)
	if events.IsSecurityError(err) {
		return
	}

	if err != nil {
		log.Println("unknown error during file open: ", err.Error())
	}
}

func LFIMultiple(w http.ResponseWriter, r *http.Request) {
	for _, path := range []string{
		parseRASPRequest(r, "file1"),
		parseRASPRequest(r, "file2"),
		"../etc/passwd",
	} {
		if path == "" {
			return
		}

		_, err := os.ReadFile(path)
		if events.IsSecurityError(err) {
			return
		}

		if err != nil {
			log.Println("unknown error during file open: ", err.Error())
		}
	}
}

func SSRF(w http.ResponseWriter, r *http.Request) {
	path := parseRASPRequest(r, "domain")
	if path == "" {
		return
	}

	req, err := http.NewRequest("GET", "http://"+path, nil)
	if err != nil {
		w.WriteHeader(500)
		log.Fatalln(err.Error())
		return
	}

	_, err = httptrace.WrapClient(http.DefaultClient).Do(req.WithContext(r.Context()))
	if events.IsSecurityError(err) {
		return
	}

	if err != nil {
		log.Println("unknown error during http call: ", err.Error())
	}
}

func SQLi(w http.ResponseWriter, r *http.Request) {
	sqli := parseRASPRequest(r, "user_id")
	if sqli == "" {
		return
	}

	db, err := sqltrace.Open("sqlite3", ":memory:")
	if err != nil {
		w.WriteHeader(500)
		log.Fatalln(err.Error())
		return
	}

	defer db.Close()

	if _, err = db.Exec("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)"); err != nil {
		log.Fatalln(err.Error())
	}

	_, err = db.ExecContext(r.Context(), "SELECT * FROM users WHERE id='"+sqli+"'")
	if events.IsSecurityError(err) {
		return
	}

	if err != nil {
		log.Println("unknown error during sql call: ", err.Error())
	}
}
