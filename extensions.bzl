load('//repository:def.bzl', 'elm_repository')


def _load_external_sources(module_ctx):
    all_deps = {}
    for mod in module_ctx.modules:
        for file in mod.tags.from_file:
            deps_file = module_ctx.read(file.deps_index)
            all_deps.update(json.decode(deps_file))
    for key in all_deps:
        value = all_deps[key]
        elm_repository(
            name = key,
            urls = [ value['url']],
            strip_prefix = value['strip_prefix'],
            sha256 = value['sha256'],
            type = value['type'],
            deps = value['deps'],
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
