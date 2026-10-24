"""Plan a fixed, benign Solidity smoke test; never install or execute anything."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[2]
IMAGE = re.compile(r"[a-z0-9][a-z0-9./_-]*@sha256:[a-f0-9]{64}\Z")


def plan(image=None, runtime=None):
    if image is not None and not IMAGE.fullmatch(image):
        raise ValueError('Use a registry image pinned by sha256 digest, not a mutable tag')
    if runtime not in (None, 'docker', 'podman'):
        raise ValueError('Unsupported container runtime')
    executable = shutil.which(runtime) if runtime else next(
        (p for name in ('docker', 'podman') if (p := shutil.which(name))), None)
    fixture = ROOT / 'tests/runtime'
    if any(p.is_symlink() for p in (fixture, *fixture.parents)):
        raise ValueError('Fixture path must have no symlink ancestors')
    hashes = {}
    for relative in ('foundry.toml', 'test/Smoke.t.sol'):
        path = fixture / relative
        if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file() or ',' in str(path):
            raise ValueError('Expected regular smoke fixture files')
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    command = None
    if executable and image:
        command = [executable, 'run', '--rm', '--pull=never', '--network=none',
                   '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                   '--user=65534:65534', '--pids-limit=128', '--memory=512m', '--cpus=1',
                   '--tmpfs=/tmp:rw,nosuid,nodev,size=128m,mode=1777',
                   '--mount', f'type=bind,src={fixture / "foundry.toml"},dst=/input/foundry.toml,readonly',
                   '--mount', f'type=bind,src={fixture / "test/Smoke.t.sol"},dst=/input/Smoke.t.sol,readonly',
                   '--env=HOME=/tmp', '--entrypoint=/bin/sh', image, '-c',
                   'mkdir -p /tmp/project/test && cp /input/foundry.toml /tmp/project/ && '
                   'cp /input/Smoke.t.sol /tmp/project/test/ && '
                   'cd /tmp/project && forge test --offline --use /usr/local/bin/solc']
    return {'schema_version': 'hindsight.runtime-plan.v1', 'status': 'not_run',
            'runtime_executable': executable, 'image': image, 'command': command,
            'fixture_sha256': hashes,
            'requirements': ['A local Docker or Podman daemon; remote daemons are not supported.',
                             'Image already present locally and containing /bin/sh, forge and /usr/local/bin/solc 0.8.20.',
                             'Run from a disposable environment without credentials; use a local runtime socket only.',
                             'This plans benign fixture tests, not reproduction of a historical exploit or detection benchmarking.'],
            'limitations': ['No daemon, image, compiler or runtime execution was checked by this command.',
                            'The plan performs no pulls, package installs, network requests or subprocess execution.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', help='Optional already-installed registry image@sha256:digest')
    parser.add_argument('--runtime', choices=['docker', 'podman'])
    args = parser.parse_args()
    try:
        result = plan(args.image, args.runtime)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
