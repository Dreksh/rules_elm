
def _elm_init_impl(ctx):
    output_file = ctx.actions.declare_file(ctx.label.name)
    executor = ctx.toolchains['//elm:toolchain'].elm[DefaultInfo]\
        .files.to_list()[0]
    print(executor.short_path)
    ctx.actions.write(
        output = output_file,
        content = """
        #!/bin/bash
        EXEC_PATH="${{PWD}}/{executor}"
        mkdir -p "${{BUILD_WORKSPACE_DIRECTORY}}/${{1}}"
        cd "${{BUILD_WORKSPACE_DIRECTORY}}/${{1}}"
        echo "== Setting up in $(pwd)"
        "${{EXEC_PATH}}" init 
        touch BUILD.bazel
        """.format(
            executor = executor.short_path,
        ),
        is_executable = True,
    )
    return [DefaultInfo(
        executable = output_file,
        runfiles= ctx.runfiles(files = [executor]),
    )]

elm_init = rule(
    implementation = _elm_init_impl,
    attrs = {},
    toolchains = [Label("//elm:toolchain")],
    executable = True,
)
