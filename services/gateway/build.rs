fn main() -> Result<(), Box<dyn std::error::Error>> {
    let proto_root = "../../proto/autoniix";

    std::fs::create_dir_all("src/generated")?;

    tonic_build::configure()
        .build_server(true)
        .build_client(false)
        .out_dir("src/generated")
        .compile(
            &[
                &format!("{proto_root}/common/v1/common.proto"),
                &format!("{proto_root}/gateway/v1/auth.proto"),
                &format!("{proto_root}/gateway/v1/jobs.proto"),
            ],
            &["../../proto"],
        )?;

    Ok(())
}
