load("@bazel_tools//tools/build_defs/repo:utils.bzl", _patch = "patch")

def _generate_build_files(repository_ctx):
    elm_text_result = repository_ctx.execute(['cat', 'elm.json'])
    elm_json = json.decode(elm_text_result.stdout)
    deps = [ '@{repo}//:library'.format(repo=repo) for repo in repository_ctx.attr.deps ]
    full_repo_name = repository_ctx.name.split('~')
    repo_name = full_repo_name[0]
    package_name = full_repo_name[-1]
    if package_name.startswith('elm_package_elm_'): # assume this is from elm/ or elm-explorations/
        return """load("@{repo_name}//elm:def.bzl", "elm_package")

elm_package(
    name = "library",
    srcs = [
        "elm.json",
    ] + glob([
        "**/*.elm",
        "**/*.js",
    ]),
    deps = {deps},
    package_name = "{name}",
    package_version = "{version}",
    visibility = ["//visibility:public"],
)""".format(
            repo_name = repo_name,
            deps = json.encode(deps),
            name = elm_json['name'],
            version = elm_json['version'],
        )
    else:
        return """load("@{repo_name}//elm:def.bzl", "elm_library")

elm_library(
    name = "library",
    srcs = glob(["src/**/*.elm"]),
    deps = {deps},
    strip_import_prefix = "src",
    visibility = ["//visibility:public"],
)""".format(
            repo_name = repo_name,
            deps = json.encode(deps),
        )

def _elm_repository_impl(repository_ctx):
    repository_ctx.download_and_extract(
        url = repository_ctx.attr.urls,
        sha256 = repository_ctx.attr.sha256,
        type = repository_ctx.attr.type,
        stripPrefix = repository_ctx.attr.strip_prefix,
    )
    _patch(repository_ctx)
    repository_ctx.file(
        'BUILD.bazel',
        content = _generate_build_files(repository_ctx),
    )

elm_repository = repository_rule(
    attrs = {
        # Download and extraction.
        "urls": attr.string_list(),
        "strip_prefix": attr.string(),
        "type": attr.string(),
        "sha256": attr.string(),
        "deps": attr.string_list(),

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
