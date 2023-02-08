#r "nuget: Newtonsoft.Json, 13.0.1"

open System
open System.Runtime.InteropServices

module NativeTypes =
    [<type: StructLayout(LayoutKind.Sequential)>]
    type DdWafVersionStruct =
        class 
            val mutable public Major: uint16
            val mutable public Minor: uint16
            val mutable public Patch: uint16
            new() = {
                Major = (uint16)0
                Minor = (uint16)0
                Patch = (uint16)0
            }
        end
        override this.ToString() =
            $"{this.Major.ToString()}.{this.Major.ToString()}.{this.Major.ToString()}"


module Native =
    [<DllImport("ddwaf.so")>]    
    extern IntPtr ddwaf_get_version()

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
        let buffer = Native.ddwaf_get_version()
        Console.WriteLine("buffer ok")
        // just to try directly
        let ddWafVersionStruct =  new NativeTypes.DdWafVersionStruct()
        Marshal.PtrToStructure(buffer, ref ddWafVersionStruct);
        Console.WriteLine(t.ToString())
        let version = 
            if assem.GetName().Version.Major <= 2 && assem.GetName().Version.Minor <= 13 then Marshal.PtrToStructure<NativeTypes.DdWafVersionStruct>(buffer).ToString() 
            else Console.WriteLine("higher version"); Marshal.PtrToStringAnsi(buffer)
        Console.WriteLine("version is" + version)
        File.WriteAllText("/app/SYSTEM_TESTS_LIBDDWAF_VERSION", version)

    writeRulesVersion ()
    writeWafVersion ()