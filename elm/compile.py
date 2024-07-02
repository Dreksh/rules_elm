import json
import os
import shutil
import struct
import subprocess
import sys

# Bazel performs some garbage collection,
# To allow multiple calls to os.makedirs (which will do nothing if it exists)
# We need to clean it up after running
class TempDir:
    PACKAGES_DIR = "elm-home/0.19.0/package"
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        self._clear_directories()
        os.makedirs(self.full_path())
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self._clear_directories()
        # Perform cleanup, but don't suppress errors
        if exception_value:
            raise exception_value

    def _clear_directories(self):
        shutil.rmtree(self.path, ignore_errors=True)

    def full_path(self):
        return self.path + "/" + TempDir.PACKAGES_DIR


(
    arg_compilation_mode,
    arg_elm_binary,
    arg_elm_json,
    arg_main,
    arg_out_js,
    arg_out_elmi,
    arg_temp_dir,
) = sys.argv[1:8]


with TempDir(arg_temp_dir) as temp_dir:

    # Construct an ELM_HOME directory, containing symlinks to all the
    # packages we want to be available to the build.
    all_packages = []
    for package_dir in sys.argv[8:]:
        with open(os.path.join(package_dir, "elm.json")) as f:
            metadata = json.load(f)
        all_packages.append((metadata["name"].split("/", 1), metadata["version"]))

        internal_package_dir = os.path.join(temp_dir.full_path(), metadata["name"])
        os.makedirs(internal_package_dir)
        os.symlink(
            os.path.abspath(package_dir),
            os.path.join(internal_package_dir, metadata["version"]),
        )

    def str_to_bytes(s):
        try:
            return bytes(s, encoding="ASCII")
        except TypeError:
            return bytes(s)


    # Generate a versions.dat package index file. Without it, Elm will be
    # dependent on internet access. Let the package index file contain just
    # those packages that are available to the build.
    with open(os.path.join(temp_dir.full_path(), "versions.dat"), "wb") as f:
        f.write(struct.pack(">QQ", len(all_packages), len(all_packages)))
        for name_parts, version in sorted(all_packages):
            version_parts = version.split(".", 2)
            f.write(struct.pack(">Q", len(name_parts[0])))
            f.write(str_to_bytes(name_parts[0]))
            f.write(struct.pack(">Q", len(name_parts[1])))
            f.write(str_to_bytes(name_parts[1]))
            f.write(
                struct.pack(
                    ">QBBB",
                    1,
                    int(version_parts[0]),
                    int(version_parts[1]),
                    int(version_parts[2]),
                )
            )

    # Cause a hard failure in case Elm tries to bypass our packages.
    elm_home = os.path.join(temp_dir.path, "elm_home")
    for root, dirs, files in os.walk(elm_home):
        os.chmod(root, 0o500)


    # Convert Bazel compilation mode to flags for 'elm make'.
    opt_flags = {"dbg": ["--debug"], "fastbuild": [], "opt": ["--optimize"]}[
        arg_compilation_mode
    ]

    # Invoke Elm build action.
    os.symlink(arg_elm_json, "elm.json")
    exit_code = subprocess.call(
        [arg_elm_binary, "make", "--output=" + arg_out_js, arg_main] + opt_flags,
        env={"ELM_HOME": elm_home },
        stdout=open(os.devnull, "w"),
    )
    if exit_code != 0:
        sys.exit(exit_code)

    # Preserve the .elmi file. This file contains information about
    # top-level declarations in the source file. It is used by elm_test() to
    # automatically generate an entry point that invokes all unit tests.
    if arg_out_elmi != "":
        elmi_file = os.path.basename(arg_main)
        if elmi_file.endswith(".elm"):
            elmi_file = elmi_file[:-4]
        elmi_file += ".elmi"
        os.rename(os.path.join("elm-stuff/0.19.0", elmi_file), arg_out_elmi)
