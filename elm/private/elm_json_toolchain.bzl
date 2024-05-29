def _elm_json_toolchain_impl(ctx):
    return [platform_common.ToolchainInfo(
        elm_json = ctx.attr.elm_json,
    )]

_elm_json_toolchain = rule(
    attrs = {
        "elm_json": attr.label(
            allow_files = True,
            mandatory = True,
        ),
    },
    implementation = _elm_json_toolchain_impl,
)

def elm_json_toolchain(name, exec_compatible_with):
    toolname = name + "_info"
    _elm_json_toolchain(
        name = toolname,
        elm_json = "@com_github_elm_%s//:elm-json" % name,
        visibility = ["//visibility:public"],
    )

    native.toolchain(
        name = name,
        toolchain_type = Label("//elm:json_toolchain"),
        exec_compatible_with = exec_compatible_with,
        toolchain = toolname,
    )
