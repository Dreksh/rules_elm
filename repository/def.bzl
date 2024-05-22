load("@bazel_tools//tools/build_defs/repo:utils.bzl", _patch = "patch")

def _elm_repository_impl(ctx):
    ctx.download_and_extract(
        url = ctx.attr.urls,
        sha256 = ctx.attr.sha256,
        type = ctx.attr.type,
        stripPrefix = ctx.attr.strip_prefix,
    )
    _patch(ctx)

    result = ctx.execute([
        ctx.executable._script.path,
        ctx.name,
    ])
    if result.return_code:
        fail("failed to generate BUILD files for %s: %s" %
             (ctx.name, result.stderr))

elm_repository = repository_rule(
    attrs = {
        # Download and extraction.
        "urls": attr.string_list(),
        "strip_prefix": attr.string(),
        "type": attr.string(),
        "sha256": attr.string(),

        # Patches to apply after extraction.
        "patches": attr.label_list(),
        "patch_tool": attr.string(default = "patch"),
        "patch_args": attr.string_list(default = ["-p0"]),
        "patch_cmds": attr.string_list(default = []),

        # Script for generating build files
        "_script": attr.label(
            cfg = "host",
            executable = True,
            default = Label("//repository:generate_build_files"),
        )
    },
    implementation = _elm_repository_impl,
)
