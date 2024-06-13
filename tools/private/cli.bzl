
def _elm_cmd_impl(ctx):
    output_file = ctx.actions.declare_file(ctx.label.name)
    executor = ctx.toolchains['//elm:toolchain'].elm.files.to_list()[0]
    ctx.actions.write(
        output = output_file,
        content = """
        #!/bin/bash
        EXEC_PATH="${{PWD}}/{executor}"
        mkdir -p "${{BUILD_WORKSPACE_DIRECTORY}}/${{1}}"
        cd "${{BUILD_WORKSPACE_DIRECTORY}}/${{1}}"
        "${{EXEC_PATH}}" {cmd} "${{@:2}}"
        {postprocess}
        """.format(
            executor = executor.short_path,
            cmd = ctx.attr.cmd,
            postprocess = ctx.attr.postprocess,
        ),
        is_executable = True,
    )
    return [DefaultInfo(
        executable = output_file,
        runfiles= ctx.runfiles(files = [executor]),
    )]

elm_cmd = rule(
    implementation = _elm_cmd_impl,
    attrs = {
        "cmd": attr.string(
            doc = "The subcommand to run in the Elm CLI",
            mandatory = True,
        ),
        "postprocess": attr.string(
            doc = "Additional commands to run in the shell afterwards",
            default = "",
        ),
    },
    toolchains = [Label("//elm:toolchain")],
    executable = True,
)
