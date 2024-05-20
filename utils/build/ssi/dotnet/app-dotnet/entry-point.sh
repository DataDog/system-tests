#!/bin/bash

dotnet restore
dotnet build -c Release
dotnet publish -c Release -o .
dotnet MinimalWebApp.dll