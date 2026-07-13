use std::path::PathBuf;

fn main() {
    // libddtracego.dylib lives one level up (adapters/dd-trace-go/).
    let dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .to_path_buf();
    println!("cargo:rustc-link-search=native={}", dir.display());
    println!("cargo:rustc-link-lib=dylib=ddtracego");
    // so the binary finds the dylib at runtime without DYLD_LIBRARY_PATH
    println!("cargo:rustc-link-arg=-Wl,-rpath,{}", dir.display());
}
