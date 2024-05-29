def _update_bazel_deps_impl(ctx):
    output_file = ctx.actions.declare_file(ctx.label.name)
    elm_json = ctx.toolchains['//elm:json_toolchain'].elm_json.files.to_list()[0]
    executor = ctx.executable._script
    ctx.actions.write(
        output = output_file,
        content = """
        #!/bin/bash
        EXEC_PATH="${{PWD}}/{executor}"
        ELM_JSON_PATH="${{PWD}}/{elm_json}"
        ${{EXEC_PATH}} @{repo_name} ${{ELM_JSON_PATH}}
        """.format(
            executor = executor.short_path,
            elm_json = elm_json.short_path,
            repo_name = ctx.attr.current_repo,
        ),
        is_executable = True,
    )
    runfiles = ctx.runfiles(files = [executor, elm_json])
    runfiles = runfiles.merge(ctx.attr._script[DefaultInfo].default_runfiles)
    return [DefaultInfo(
        executable = output_file,
        runfiles = runfiles,
    )]

_update_bazel_deps = rule(
    implementation = _update_bazel_deps_impl,
    attrs = {
        '_script': attr.label(
            cfg = "host",
            default = "//tools/private:update_bazel_deps",
            executable = True,
        ),
        'current_repo': attr.string(),
    },
    toolchains = [
        Label("//elm:json_toolchain"),
    ],
    executable = True,
)

def update_bazel_deps(name, **kwargs):
    # Always overwrite to contain this repo's name
    kwargs['current_repo'] = native.repo_name().strip('~').split('~')[-1]
    _update_bazel_deps(name = name, **kwargs)
