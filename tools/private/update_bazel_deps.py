import hashlib
import io
import json
import os
import re
import requests
import subprocess
import sys
import zipfile

### Elm Dependencies

class ElmJson:
    def __init__(self, path: str):
        self.path = path

    # Returns a map of library -> set of depepndencies
    def get_deps(self, elm_dir: str):
        result = subprocess.run(
            [self.path, "tree", "--", elm_dir + "/elm.json"],
            capture_output=True,
            text = True,
        )
        if result.returncode != 0:
            raise Exception('{path}: {err}'.format(
                path = elm_dir,
                err = result.stderr,
            ))
        depmap = {}
        # returns 
        def analyse_dependency(current_str: str, it: iter) -> (set, str):
            deps = set()
            current_depth = current_str.find('─ ')
            next_line = current_str
            last_iter_lib = ''
            while next_line:
                index = next_line.find('─ ')
                if index < current_depth:
                    return (deps, next_line)
                if index > current_depth:
                    subdeps, next_line = analyse_dependency(next_line, it)
                    depmap[last_iter_lib] = subdeps
                    continue
                # parse '-- elm/core @ 1.0.2 *'
                symbols = next_line.split(' ')
                if symbols[-1] == '*':
                    symbols = symbols[:-1]
                last_iter_lib = '{lib}/{version}'.format(lib = symbols[-3], version = symbols[-1])
                deps.add(last_iter_lib)
                if last_iter_lib not in depmap: # If they don't have dependencies, they won't have subtrees
                    depmap[last_iter_lib] = set()
                next_line = next(it, None)
            return (deps, None)
        line_it = iter(result.stdout.split('\n'))
        first_line = next(line_it)
        while first_line != None and first_line.find('─ ') == -1: # First line could be an empty string
            first_line = next(line_it, None)
        if not first_line:
            raise Exception('Unexpected output from elm-json tree: {output}'.format(output = result.stdout))
        analyse_dependency(first_line, line_it)
        return depmap

class ElmDepFetcher:
    def __init__(self):
        self.url = "https://package.elm-lang.org"

    def resolve(self, pkg_version):
        print(f"fetching {pkg_version}")
        endpoint_json = requests.get('{base}/packages/{pkg_version}/endpoint.json'.format(
            base = self.url,
            pkg_version = pkg_version,
        ))
        if endpoint_json.status_code != 200:
            raise Exception(f"endpoint.json is not found for {pkg_verison}")
        info = endpoint_json.json()
        if not info or not info['url']:
            raise Exception(f"unexpected endpoint.json format for {pkg_verison}")
        pkg = requests.get(info['url'])
        if pkg.status_code >= 400:
            raise Exception(f"got {pkg.status_code} download {info.url} for {pkg_version}")
        sha_hash = hashlib.sha256(pkg.content).hexdigest()
        prefix = ""
        with zipfile.ZipFile(io.BytesIO(pkg.content)) as zip_file:
            children = list(zipfile.Path(root = zip_file).iterdir())
            if len(children) != 1:
                raise Exception(f"multiple root nodes in {info.url} for {pkg_version}")
            prefix = children[0].name
        content_type = pkg.headers['content-type']
        if content_type == 'application/zip':
            content_type = 'zip'
        else:
            raise Exception(f"unknown content type for {info.url}: {content_type}")
        return {
            "url": info['url'],
            "strip_prefix": prefix,
            "sha256": sha_hash,
            "type": content_type,
        }

### File modifiers

def bazel_repo(libVer):
    return "elm_package_" + re.sub("\.|-|/", "_", libVer)

def update_file(filepath, depmap, *text_modifiers):
    text = ""
    try:
        with open(filepath, 'r') as fd:
            text = fd.read()
    except FileNotFoundError as e:
        print('Creating {file}'.format(file = filepath))
    for mod in text_modifiers:
        text = mod.update_text(depmap, text)
    with open(filepath, 'w') as fd:
        fd.write(text)

class TextModifier:
    def __init__(self, region_of_interest):
        self.region_of_interest = region_of_interest

    def _extract(self, text):
        match = re.search(self.region_of_interest, text, re.MULTILINE)
        if not match:
            return len(text), len(text) # Default is to place it at the end
        return match.span()

    def _extract_context(self, text):
        return None
        
    def update_text(self, depmap, text):
        start, end = self._extract(text)
        context = self._extract_context(text[start:end])
        new_block = self._compose(depmap, context)
        return text[:start] + new_block + text[end:]

class BuildElmLibraryModifier(TextModifier):
    def __init__(self, repo_name):
        super().__init__(r"^elm_library\((.*\n)*?^\)")
        self.repo_name = repo_name

    def _extract_context(self, text):
        prev_match = None
        matches = {}
        for match in re.finditer(r"^(    [a-z_]|\))", text, re.MULTILINE):
            start = match.span()[0]
            if prev_match: # guard against None and 0
                line = text[prev_match:start].split('=',2)
                name = line[0].strip()
                # sepcial handling for name and deps
                if name == 'name':
                    matches['name'] = re.search(r'"(?P<name>[^"]*)"', line[1])['name']
                elif name == 'deps':
                    matches['deps'] = list(re.findall(r"^.*#keep", line[1], re.MULTILINE))
                else:
                    matches[name] = line[1].strip()
            prev_match = start
        return matches

    def _compose(self, depmap, context = None):
        context = context or {
            'srcs': 'glob(["src/**/*.elm"])+["elm.json"],',
            'strip_import_prefix': '"src",',
        } # Set defaults
        name = context.pop('name', 'library')
        deps = [ '        "@{dep}//:library",'.format(dep = bazel_repo(dep)) for dep in depmap.keys() ]
        deps.extend(context.pop('deps', []))
        deps.sort()

        others = ""
        for key in sorted(context.keys()):
            others += '    {key} = {value}\n'.format(key = key, value = context[key])
        return """elm_library(
    name = "{name}",
    deps = [
{deps}
    ],
{others})""".format(
            name = name,
            deps = '\n'.join(deps),
            others = others,
        )

class BuildElmLoadModifier(TextModifier):
    def __init__(self, repo_name):
        super().__init__(None)
        self.repo_name = repo_name

    def _extract(self, text):
        match = re.search(r"^load\(.{repo_name}//elm:def.bzl.*?\)".format(repo_name = self.repo_name), text, re.MULTILINE | re.DOTALL)
        if not match:
            # insert load statement at the top of the file
            return 0, 0
        return match.span()

    def _extract_context(self, text):
        if not text:
            return None
        if "elm_library" in text:
            return text
        # Modify existing one to include elm_library
        return text[:-1] + ', "elm_library")'

    def _compose(self, depmap, context = None):
        if context:
            return context
        # This will only trigger if the load statement wasn't there, add a newline at the end
        return 'load("{repo_name}//elm:def.bzl", "elm_library")\n'.format(repo_name = self.repo_name)
        
class ModuleElmDepsModifier(TextModifier):
    def __init__(self, repo_name):
        super().__init__(r"# elm_deps START(.*\n)*?^# elm_deps END")
        self.repo_name = repo_name

    def _extract_context(self, text):
        return re.findall(r"^.*#keep", text, re.MULTILINE)

    def _compose(self, depmap, context = None):
        all_deps = [ '    "{repo}",'.format(repo=bazel_repo(dep)) for dep in depmap.keys() ]
        if context:
            all_deps.extend(context)
        all_deps.sort()
        return """# elm_deps START
elm_repo_deps = use_extension('{repo_name}//:extensions.bzl', 'load_external_sources')
elm_repo_deps.from_file(
    deps_index = "//:elm_repos.json",
)
use_repo(
    elm_repo_deps,
{deps}
)
# elm_deps END""".format(
            repo_name = self.repo_name,
            deps = '\n'.join(all_deps),
        )

class ElmReposModifier(TextModifier):
    def __init__(self):
        super().__init__(None)
        self.dep_fetcher = ElmDepFetcher()

    def _extract(self, text):
        return 0, len(text)

    def _extract_context(self, text):
        if not text:
            return None
        try:
            return json.loads(text)
        except ValueError as e:
            print('elm_repos.json is malformed, remaking', e)

    def _compose(self, depmap, context = None):
        context = context or {}
        depset = set(map(bazel_repo, depmap.keys()))
        info = { key: context[key] for key in context if key in depset or "keep" in context[key] }
        for dep in depmap:
            repo_name = bazel_repo(dep)
            if repo_name not in info:
                resolved_map = self.dep_fetcher.resolve(dep)
                resolved_map.update({
                    'deps': sorted(map(bazel_repo, depmap[dep])),
                })
                info[repo_name] = resolved_map
        return json.dumps(info, indent = 2, sort_keys = True)

# Expected to be invoked with
# <cmd> <current repo's name> <elm_json path>
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Invalid arguments")
        exit(1)
    repo_label = sys.argv[1]
    executor = ElmJson(sys.argv[2])

    # Go to workspace
    workdir = os.environ.get('BUILD_WORKSPACE_DIRECTORY','')
    if workdir == '':
        print("Expected to be running in Bazel")
        exit(1)
    os.chdir(workdir)

    all_deps = {}
    elm_dirs = []
    loadModifier = BuildElmLoadModifier(repo_label)
    libraryModifier = BuildElmLibraryModifier(repo_label)
    for root, dirs, files in os.walk('.'):
        if root == '.':
            # Ignore directories starting with `.` or `bazel-` in the workspace root
            for index in range(len(dirs)-1, -1, -1):
                if dirs[index].startswith('.') or dirs[index].startswith('bazel-'):
                    del dirs[index]
            continue
        # Ignore directories without elm.json
        if not 'elm.json' in files:
            continue
        elm_dirs.append(root)
        
        # Get dependencies for this module
        deps = executor.get_deps(root)
        update_file(root + "/BUILD.bazel", deps, libraryModifier, loadModifier)
        all_deps.update(deps)
    update_file('MODULE.bazel', all_deps, ModuleElmDepsModifier(repo_label))
    update_file('elm_repos.json', all_deps, ElmReposModifier())
