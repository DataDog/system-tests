// Unless explicitly stated otherwise all files in this repository are licensed
// under the Apache License Version 2.0.
// This product includes software developed at Datadog (https://www.datadoghq.com/).
// Copyright 2024 Datadog, Inc.

package common

import (
	"encoding/json"
	"io"
	"log"
	"net/http"
	"strings"

	httptrace "gopkg.in/DataDog/dd-trace-go.v1/contrib/net/http"
)

func Requestdownstream(w http.ResponseWriter, _ *http.Request) {
	client := httptrace.WrapClient(http.DefaultClient)
	req, _ := http.NewRequest(http.MethodGet, "http://127.0.0.1:7777/returnheaders", nil)
	res, err := client.Do(req)
	if err != nil {
		log.Fatal(err)
	}
	defer res.Body.Close()
	io.Copy(w, res.Body)
}

func Returnheaders(w http.ResponseWriter, r *http.Request) {
	headerStrStrMap := make(map[string]string, len(r.Header))
	for key, values := range r.Header {
		headerStrStrMap[key] = strings.Join(values, ",")
	}
	jsonData, err := json.Marshal(headerStrStrMap)
	if err != nil {
		w.WriteHeader(500)
		w.Write([]byte("failed to convert headers to JSON"))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(jsonData)
}
