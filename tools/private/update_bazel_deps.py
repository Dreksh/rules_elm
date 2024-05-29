import base64
import contextlib
import hashlib
import io
import json
import os
import re
import requests
import subprocess
import sys
import zipfile

def bazel_repo(libVer):
    return re.sub("\.|-|/", "_", libVer)

class ElmJson:
    def __init__(self, path):
        self.path = path

    # Returns a set of library/version
    def get_deps(self, elm_dir):
        result = subprocess.run(
            [self.path, "solve", "--", elm_dir + "/elm.json"],
            capture_output=True,
        )
        if result.returncode != 0:
            raise Exception('{path}: {err}'.format(
                path = elm_dir,
                err = result.stderr,
            ))
        deps = json.loads(result.stdout)
        depset = set()
        for key in deps['direct']:
            depset.add('{key}/{value}'.format(key=key, value=deps['direct'][key]))
        for key in deps['indirect']:
            depset.add('{key}/{value}'.format(key=key, value=deps['indirect'][key]))
        return depset

class FileModifier:
    def __init__(self, filepath):
        self._filepath = filepath
        self._text = None

    @staticmethod
    def file_wrapper(func):
        def wrapper(self, depset):
            text = ""
            try:
                with open(self._filepath, 'r') as fd:
                    text = fd.read()
            except FileNotFoundError as e:
                print('Creating {file}'.format(file = self._filepath))
            text = func(self, depset, text)
            with open(self._filepath, 'w') as fd:
                fd.write(text)
        return wrapper

    @file_wrapper
    def update_file(self, depset, text):
        start, end = self._region_of_interest(text)
        if start != -1:
            additional_deps = self._extract_additional_deps(text[start:end])
            new_block = self._compose(depset, additional_deps)
        else:
            start, end = len(text), len(text) # Match at the very end, since we'll append
            new_block = self._compose(depset, None)
        text = text[:start] + new_block + text[end:]

        expected_line = self._expected_line()
        if expected_line and expected_line not in text:
            text = expected_line + text # Assume this is a load statement
        return text

class BuildFile(FileModifier):
    def __init__(self, directory, repo_name):
        super().__init__(directory + "/BUILD.bazel")
        self.repo_name = repo_name
        self.is_library = False # default to expecting the package is a binary
        paths = directory.strip('/').split('/')
        if not len(paths):
            self.name = "binary"
        else:
            self.name = paths[-1]

    def _region_of_interest(self, text):
        match = re.search(r"^elm_(binary|library)\((.*\n)*?^\)", text, re.MULTILINE)
        if not match:
            return -1, -1
        start, end = match.span()
        self.is_library = 'elm_binary' in text[start:start+11]
        return start, end

    def _extract_additional_deps(self, text):
        # Assume they're all from the deps section of elm_(binary|library)
        matches = re.findall("\n.*?, *#keep", text)
        return set(matches)

    def _compose(self, depset, additional_deps = None):
        deps = [ '        "@{dep}//:library",'.format(dep = bazel_repo(dep)) for dep in list(depset) ]
        if additional_deps:
            deps.extend(list(additional_deps))
        deps.sort()
        return """{rule}(
    name = "{name}",
    srcs = glob(["**/*.elm"]),
    deps = [
{deps}
    ],
)""".format(
            rule = "elm_library" if self.is_library else "elm_binary",
            deps = '\n'.join(deps),
            name = self.name,
        )
        
    # needs to be called after _region_of_interest to have is_library populated correctly
    def _expected_line(self):
        return 'load("{repo}//elm:def.bzl", "{type}")\n'.format(
            repo = self.repo_name,
            type = "elm_library" if self.is_library else "elm_binary",
        )
        
class ModuleFile(FileModifier):
    def __init__(self, repo_name):
        super().__init__("MODULE.bazel")
        self.repo_name = repo_name

    def _region_of_interest(self, text):
        match = re.search(r"# elm_deps START(.*\n)*?^# elm_deps END", text, re.MULTILINE)
        if not match:
            print('HERE')
            return -1, -1
        return match.span()

    def _extract_additional_deps(self, text):
        return None

    def _compose(self, depset, additional_deps = None):
        if additional_deps:
            depset.union(additional_deps)
        all_deps = list(depset)
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
            deps = '\n'.join([ '    "{repo}",'.format(repo=bazel_repo(dep)) for dep in all_deps ]),
        )
        
    def _expected_line(self):
        return None

class ElmReposFile(FileModifier):
    def __init__(self):
        super().__init__("elm_repos.json")
        self.dep_fetcher = ElmDepFetcher()

    def _region_of_interest(self, text):
        return (0, len(text))

    def _extract_additional_deps(self, text):
        if not text:
            return None
        try:
            existing_repo_map = json.loads(text)
            return { key: value for key, value in existing_repo_map if "keep" in value }
        except ValueError as e:
            print('elm_repos.json is malformed, remaking')

    def _compose(self, depset, additional_deps = None):
        info = additional_deps or {}
        for dep in all_deps:
            info[bazel_repo(dep)] = self.dep_fetcher.resolve(dep)
        return json.dumps(info)
        
    def _expected_line(self):
        return None

class ElmDepFetcher:
    def __init__(self):
        self.url = "https://package.elm-lang.org"

    def resolve(self, pkg_version):
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
        sha_hash = base64.b64encode(hashlib.sha256(pkg.content).digest()).decode('utf-8')
        print(f"got type {pkg.headers['content-type']} for {pkg_version}")
        prefix = ""
        with zipfile.ZipFile(io.BytesIO(pkg.content)) as zip_file:
            children = list(zipfile.Path(root = zip_file).iterdir())
            if len(children) != 1:
                raise Exception(f"multiple root nodes in {info.url} for {pkg_version}")
            prefix = children[0].name

        return {
            "url": info['url'],
            "strip_prefix": prefix,
            "sha256": sha_hash,
        }

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

    all_deps = set()
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
        # Get dependencies for this module
        deps = executor.get_deps(root)
        BuildFile(root, repo_label).update_file(deps)
        all_deps = all_deps.union(deps)
    ModuleFile(repo_label).update_file(all_deps)
    ElmReposFile().update_file(all_deps)
