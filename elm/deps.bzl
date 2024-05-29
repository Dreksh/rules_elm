load("@bazel_tools//tools/build_defs/repo:http.bzl", _http_archive = "http_archive")

def _fetch_compiler_archives(module_ctx):
    # Elm CLI
    _http_archive(
        name = "com_github_elm_compiler_linux",
        build_file_content = """exports_files(["elm"])""",
        sha256 = "7a82bbf34955960d9806417f300e7b2f8d426933c09863797fe83b67063e0139",
        urls = ["https://github.com/elm/compiler/releases/download/0.19.0/binaries-for-linux.tar.gz"],
    )

    _http_archive(
        name = "com_github_elm_compiler_mac",
        build_file_content = """exports_files(["elm"])""",
        sha256 = "18410e605208fc2b620f5e30bccbbd122c992a27de46f9f362271ce3dcc66962",
        urls = ["https://github.com/elm/compiler/releases/download/0.19.0/binaries-for-mac.tar.gz"],
    )

    # Elm JSON
    _http_archive(
        name = "com_github_elm_json_darwin_arm",
        build_file_content = """exports_files(["elm-json"])""",
        sha256 = "4d917f21e40badc6d8f0f61e4cc0690e56b62c8c4280f379ead8da8e18de1760",
        urls = ["https://github.com/zwilias/elm-json/releases/download/v0.2.13/elm-json-v0.2.13-aarch64-apple-darwin.tar.gz"],
    )
    _http_archive(
        name = "com_github_elm_json_darwin_x86",
        build_file_content = """exports_files(["elm-json"])""",
        sha256 = "868d82cc5496ddc5e17303e85b198b29fe7a30c8ac8b22aa9607e23cc07a1884",
        urls = ["https://github.com/zwilias/elm-json/releases/download/v0.2.13/elm-json-v0.2.13-x86_64-apple-darwin.tar.gz"],
    )
    _http_archive(
        name = "com_github_elm_json_linux_arm",
        build_file_content = """exports_files(["elm-json"])""",
        sha256 = "acc093b8a5037f141c7870ec6d8bb1140b37031ccf4e99cea0280864d7f4831e",
        urls = ["https://github.com/zwilias/elm-json/releases/download/v0.2.13/elm-json-v0.2.13-armv7-unknown-linux-musleabihf.tar.gz"],
    )
    _http_archive(
        name = "com_github_elm_json_linux_x86",
        build_file_content = """exports_files(["elm-json"])""",
        sha256 = "83cbab79f6c237d3f96b69baf519bdd7634d0e0373a390594d37591c0295f965",
        urls = ["https://github.com/zwilias/elm-json/releases/download/v0.2.13/elm-json-v0.2.13-x86_64-unknown-linux-musl.tar.gz"],
    )

    # Repo for testing
    _http_archive(
        name = "com_github_rtfeldman_node_test_runner",
        build_file_content = """load("@rules_elm//elm:def.bzl", "elm_library")

elm_library(
    name = "node_test_runner",
    srcs = glob(["src/**/*.elm"]),
    strip_import_prefix = "src",
    visibility = ["//visibility:public"],
)""",
        sha256 = "0a674bc62347b8476a4d54e432a65f49862278a9062fd86948dfafafb96c511d",
        strip_prefix = "node-test-runner-0.19.0",
        urls = ["https://github.com/rtfeldman/node-test-runner/archive/0.19.0.tar.gz"],
    )

def elm_register_toolchains():
    _fetch_compiler_archives(None)
    native.register_toolchains(Label("//elm/toolchain:linux"))
    native.register_toolchains(Label("//elm/toolchain:mac"))

elm_toolchain_extension = module_extension(
    implementation = _fetch_compiler_archives,
    doc = "Downloads the required binaries for the elm rules",
)
