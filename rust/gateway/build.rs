fn main() -> Result<(), Box<dyn std::error::Error>> {
    let proto_root = "../../proto/autoniix";
    
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
