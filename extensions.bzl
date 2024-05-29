load('//repository:def.bzl', 'elm_repository')


def _load_external_sources(module_ctx):
    all_deps = {}
    for mod in module_ctx.modules:
        for file in mod.tags.from_file:
            deps_file = module_ctx.read(file.file.deps_index)
            all_deps.update(json.decode(deps_file))
    for key in all_deps:
        elm_repoitory(
            name = key,
            urls = [ all_deps['key']['url']],
            strip_prefix = [ all_deps['key']['strip_prefix']],
            sha256 = [ all_deps['key']['sha256']],
        )

load_external_sources = module_extension(
    implementation = _load_external_sources,
    tag_classes = {
        'from_file': tag_class (
            attrs = {
                'deps_index': attr.label(
                    allow_single_file = True,
                    mandatory = True,
                )
            }
        ),
    },
)
