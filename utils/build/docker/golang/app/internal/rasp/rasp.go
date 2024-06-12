package rasp

import (
	"encoding/json"
	"encoding/xml"
	"errors"
	"github.com/mattn/go-sqlite3"
	"gopkg.in/DataDog/dd-trace-go.v1/appsec"
	"gopkg.in/DataDog/dd-trace-go.v1/appsec/events"
	"gopkg.in/DataDog/dd-trace-go.v1/contrib/database/sql"
	httptrace "gopkg.in/DataDog/dd-trace-go.v1/contrib/net/http"
	"log"
	"net/http"
	"os"
)

func parseRASPRequest(w http.ResponseWriter, r *http.Request, key string) string {
	var input string

	switch r.Method {
	case http.MethodPost:
		input = r.URL.Query().Get("file")
	case http.MethodGet:
		var (
			body map[string]string
			err  error
		)
		switch r.Header.Get("Content-Type") {
		case "application/json":
			err = json.NewDecoder(r.Body).Decode(&body)
		case "application/xml":
			err = xml.NewDecoder(r.Body).Decode(&body)
		case "application/x-www-form-urlencoded":
			err = r.ParseForm()
			body[key] = r.Form.Get("file")
		default:
			err = errors.New("unsupported content type")
		}
		if err != nil {
			w.WriteHeader(400)
			log.Fatalf("failed to parse body: %v\n", err)
			return ""
		}

		appsec.MonitorParsedHTTPBody(r.Context(), body)
		input = body[key]
	default:
		w.WriteHeader(405)
		return ""
	}

	if len(input) == 0 {
		w.WriteHeader(422)
		log.Fatalln("missing required parameter")
		return ""
	}

	return input
}

func LFI(w http.ResponseWriter, r *http.Request) {
	path := parseRASPRequest(w, r, "file")
	if path == "" {
		return
	}

	_, err := os.ReadFile(path)
	if events.IsSecurityError(err) {
		return
	}

	if err != nil {
		w.WriteHeader(500)
		log.Fatalln([]byte(err.Error()))
		return
	}
}

func SSRF(w http.ResponseWriter, r *http.Request) {
	path := parseRASPRequest(w, r, "domain")
	if path == "" {
		return
	}

	req, err := http.NewRequest("GET", "http://"+path, nil)
	if err != nil {
		w.WriteHeader(500)
		log.Fatalln([]byte(err.Error()))
		return
	}

	_, err = httptrace.WrapClient(http.DefaultClient).Do(req.WithContext(r.Context()))
	if events.IsSecurityError(err) {
		return
	}

	if err != nil {
		w.WriteHeader(500)
		log.Fatalln([]byte(err.Error()))
		return
	}
}

func SQLi(w http.ResponseWriter, r *http.Request) {
	sqli := parseRASPRequest(w, r, "user_id")
	if sqli == "" {
		return
	}

	sql.Register("sqlite3", &sqlite3.SQLiteDriver{})
	db, err := sql.Open("sqlite3", ":memory:")
	if err != nil {
		w.WriteHeader(500)
		log.Fatalln([]byte(err.Error()))
		return
	}

	defer db.Close()

	_, err = db.Exec("SELECT * FROM users WHERE id = " + sqli)
	if events.IsSecurityError(err) {
		return
	}

	if err != nil {
		w.WriteHeader(500)
		log.Fatalln([]byte(err.Error()))
		return
	}
}
