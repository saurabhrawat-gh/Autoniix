fn main() -> Result<(), Box<dyn std::error::Error>> {
    let proto_root = "../../proto/autoniix";
    
    // The output directory is gitignored (generated code is a build artifact),
    // so it may not exist on a fresh checkout / in CI. Create it before tonic
    // writes into it, otherwise the build fails with a NotFound error.
    std::fs::create_dir_all("src/generated")?;
    
    tonic_build::configure()
        .build_server(true)
        .build_client(false)
        .out_dir("src/generated")
        .compile(
            &[
                &format!("{}/common/v1/common.proto", proto_root),
                &format!("{}/gateway/v1/auth.proto", proto_root),
                &format!("{}/gateway/v1/jobs.proto", proto_root),
            ],
            &["../../proto"],
        )?;
    
    Ok(())
}
