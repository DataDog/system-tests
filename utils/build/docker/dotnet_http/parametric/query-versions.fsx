#r "nuget: Newtonsoft.Json, 13.0.1"
#nowarn "9"

open System
open System.Runtime.InteropServices
open Microsoft.FSharp.NativeInterop

// <= waf1.3.0 it was a struct and not a string, < tracer version 15
module NativeOld =
    [<DllImport("ddwaf.so")>]    
    extern IntPtr ddwaf_get_version(nativeint version)

module Native =
    [<DllImport("ddwaf.so")>]
    extern IntPtr ddwaf_get_version()

module QueryVersions =
    open System
    open System.IO
    open System.Reflection
    open Newtonsoft.Json
    open Newtonsoft.Json.Linq

    [<Struct>]
    [<StructLayout(LayoutKind.Sequential, Pack=1)>]
    type WafVersion =
        struct 
            val mutable Major: uint16
            val mutable Minor: uint16
            val mutable Patch: uint16
        end
        override this.ToString() =
            $"{this.Major.ToString()}.{this.Minor.ToString()}.{this.Patch.ToString()}"

    let unknownRulesDefault = "1.2.5"
    let assem = Assembly.LoadFrom("/opt/datadog/netcoreapp3.1/Datadog.Trace.dll")
   
    let writeRulesVersion () =
        let ruleVersion =
            let mutable stream = assem.GetManifestResourceStream("Datadog.Trace.AppSec.Waf.rule-set.json")
            if stream = null then
                stream <- assem.GetManifestResourceStream("Datadog.Trace.AppSec.Waf.ConfigFiles.rule-set.json")
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
        let getOldWafVersion () =
            let mutable ver:WafVersion = WafVersion()
            let verPtr = &&ver
            let nativeInt = NativePtr.toNativeInt verPtr
            NativeOld.ddwaf_get_version(nativeInt) |> ignore
            ver.ToString()
        
        let getWafVersion () =
            let buffer = Native.ddwaf_get_version()
            Marshal.PtrToStringAnsi(buffer)
        
        let version = 
            if assem.GetName().Version.Major <= 2 && assem.GetName().Version.Minor <= 14 then getOldWafVersion()
            else getWafVersion()
        File.WriteAllText("/app/SYSTEM_TESTS_LIBDDWAF_VERSION", version)

    writeRulesVersion ()
    writeWafVersion ()