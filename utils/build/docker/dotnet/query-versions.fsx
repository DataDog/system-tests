#r "nuget: Newtonsoft.Json, 13.0.1"

module QueryVersions =
    open System
    open System.IO
    open System.Reflection
    open Newtonsoft.Json
    open Newtonsoft.Json.Linq

    let unknownRulesDefault = "1.2.5"
    let assem = Assembly.LoadFrom("/opt/datadog/netcoreapp3.1/Datadog.Trace.dll")

    let writeRulesVersion () =
        let ruleVersion =
            use stream = assem.GetManifestResourceStream("Datadog.Trace.AppSec.Waf.rule-set.json")
            use reader = new StreamReader(stream);
            use jsonReader = new JsonTextReader(reader);
            let root = JToken.ReadFrom(jsonReader);
            let metadata = root.Value<JObject>("metadata");
            if metadata = null then
                unknownRulesDefault
            else
                let ruleVersion = metadata.Value<JValue>("rules_version");
                if ruleVersion = null || ruleVersion.Value = null then
                    unknownRulesDefault
                else
                    ruleVersion.Value.ToString()
        File.WriteAllText("/app/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION", ruleVersion)

    let writeWafVersion () =
        Environment.SetEnvironmentVariable("DD_DOTNET_TRACER_HOME", "/binaries")
        let wafType = assem.GetType("Datadog.Trace.AppSec.Waf.Waf")
        let versionProp = wafType.GetProperty("Version")
        let createMethod = wafType.GetMethod("Create", BindingFlags.NonPublic ||| BindingFlags.Static)
        let waf = createMethod.Invoke(null, [| null |])
        let version = versionProp.GetValue(waf)
        File.WriteAllText("/app/SYSTEM_TESTS_LIBDDWAF_VERSION", (version.ToString()))

    File.WriteAllText("/app/DEBUG", "Yes, we can")

    writeRulesVersion ()
    writeWafVersion ()