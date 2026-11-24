# ddtrace installed from the wheel, usable with python.withPackages.
{
  lib,
  fetchPypi,
  common,
  python,
  wheel,
}:
let
  ps = python.pkgs;

  # Runtime dependencies missing from nixpkgs, taken as published wheels.
  pypiWheel =
    pname: version: hash:
    ps.buildPythonPackage {
      inherit pname version;
      format = "wheel";
      src = fetchPypi {
        pname = lib.replaceStrings [ "-" ] [ "_" ] pname;
        inherit version hash;
        format = "wheel";
        dist = "py3";
        python = "py3";
      };
    };

  envier = ps.envier or (pypiWheel "envier" "0.6.1" "sha256-c2CQQKdr5Iu8uXB02ZaWZkhKoN5wYYOm6e93MVaopqk=");
  ddtrace-internal =
    ps.ddtrace-internal or (pypiWheel "ddtrace-internal" "0.1.0"
      "sha256-jurEqBLgA866/IvjXvBRA64rEyiT37zuAKZ/SvgUBKI="
    );
in
ps.buildPythonPackage {
  inherit (common) pname version;
  format = "wheel";

  # The wheel's file name (its platform tag) is only known once it is built, so copy it in
  # instead of pointing src at it. Like wheelUnpackPhase, skip the postUnpack hooks, which expect
  # a source root.
  src = wheel;
  unpackPhase = ''
    runHook preUnpack
    mkdir dist
    cp ${wheel}/*.whl dist/
  '';

  dependencies = [
    ps.bytecode
    ps.opentelemetry-api
    ps.wrapt
    envier
    ddtrace-internal
  ];

  pythonImportsCheck = [
    "ddtrace"
    "ddtrace.internal.native._native"
  ];

  meta = {
    description = "Datadog APM client library";
    homepage = "https://github.com/DataDog/dd-trace-py";
    license = with lib.licenses; [
      bsd3
      asl20
    ];
  };
}
