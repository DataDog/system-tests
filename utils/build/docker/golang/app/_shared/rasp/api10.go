package rasp

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"strings"

	httptrace "github.com/DataDog/dd-trace-go/contrib/net/http/v2"
	"github.com/sirupsen/logrus"
)

var HTTPClient = httptrace.WrapClient(http.DefaultClient)

func ExternalRequest(w http.ResponseWriter, upwardReq *http.Request) {
	status := upwardReq.URL.Query().Get("status")
	if status == "" {
		status = "200"
	}
	url := "http://internal_server:8089/mirror/" + status + upwardReq.URL.Query().Get("url_extra")
	req, err := http.NewRequest(upwardReq.Method, url, upwardReq.Body)
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		logrus.Error("error creating request: ", err)
		return
	}

	for key, values := range upwardReq.URL.Query() {
		if key == "status" || key == "url_extra" {
			continue
		}

		req.Header.Set(key, strings.Join(values, ","))
	}

	req.Header.Set("Content-Type", "application/json")

	resp, err := HTTPClient.Do(req.WithContext(upwardReq.Context()))
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		logrus.Error("error creating request: ", err)
		return
	}

	defer resp.Body.Close()
	w.WriteHeader(200)

	var body any
	if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		logrus.Error("error creating request: ", err)
		return
	}

	if resp.StatusCode >= 400 {
		type errorResponse struct {
			Status int    `json:"status"`
			Error  string `json:"error"`
		}

		if err := json.NewEncoder(w).Encode(&errorResponse{
			Status: resp.StatusCode,
			Error:  fmt.Sprintf("url: %q, body: %v", url, body),
		}); err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			logrus.Error("error creating request: ", err)
		}

		return
	}

	type successResponse struct {
		Status  int               `json:"status"`
		Payload any               `json:"payload"`
		Headers map[string]string `json:"headers"`
	}

	headers := make(map[string]string, len(resp.Header))
	for key, values := range resp.Header {
		headers[key] = strings.Join(values, ",")
	}

	fmt.Fprintf(os.Stdout, "response headers: %v\n", headers)

	if err := json.NewEncoder(w).Encode(&successResponse{
		Status:  resp.StatusCode,
		Payload: body,
		Headers: headers,
	}); err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		logrus.Error("error creating response: ", err)
	}
}
