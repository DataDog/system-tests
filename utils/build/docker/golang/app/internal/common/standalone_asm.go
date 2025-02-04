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
)

func Requestdownstream(w http.ResponseWriter, r *http.Request) {
	client := httpClient()
	req, _ := http.NewRequest(http.MethodGet, "http://127.0.0.1:7777/returnheaders", nil)
	req = req.WithContext(r.Context())
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

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(headerStrStrMap); err != nil {
		panic(err)
	}
}
