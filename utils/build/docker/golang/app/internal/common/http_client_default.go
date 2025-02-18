// Unless explicitly stated otherwise all files in this repository are licensed
// under the Apache License Version 2.0.
// This product includes software developed at Datadog (https://www.datadoghq.com/).
// Copyright 2024 Datadog, Inc.

//go:build !orchestrion

package common

import (
	"net/http"

	httptrace "github.com/DataDog/dd-trace-go/contrib/net/http/v2"
)

func httpClient() *http.Client {
	return httptrace.WrapClient(http.DefaultClient, httptrace.WithPropagation(true))
}
