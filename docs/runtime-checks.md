# Isolated runtime checks

Source preparation and report validation check artifacts and evidence locations.
They do not compile contracts, reproduce exploits or measure detection accuracy.
Actual compilation and runtime tests must be recorded separately.

## Check what is available

```sh
python3 -I scripts/runtime/plan.py
```

This offline command reports local Docker/Podman executable availability and
fingerprints two repository-owned benign Solidity fixtures. It installs nothing,
contacts no daemon and executes no container or Solidity. Its status is always
`not_run`; executable availability does not prove that a daemon works.

## Prepare an execution plan

Use a trusted image already present locally, pinned by registry SHA-256 digest,
with `/bin/sh`, `forge`, and Solidity 0.8.20 at `/usr/local/bin/solc`:

```sh
python3 -I scripts/runtime/plan.py --runtime docker \
  --image registry.example/your-prepared-image@sha256:REPLACE_WITH_64_HEX_DIGEST
```

Replace the placeholder with a real image/digest. No image is supplied, pulled,
built or assumed verified by the planner. It emits a command only when both an
executable and a valid image identifier are supplied. The command mounts only
the two approved fixture files, uses a non-root user, disables networking and
pulls, drops capabilities, sets resource limits and uses disposable temporary
storage. No project folder, credentials, runtime socket or user environment is
mounted into the container. Review and execute that command only against a local
daemon in a disposable environment without credentials. Remote daemons are not
supported; the planner does not inspect daemon context or certify the image.

The fixture checks normal credit accounting and rejection of an excessive
removal. It is not exploit code, a reentrancy reproduction or a benchmark.
Record the executed command, image identity, fixture hashes, actual compiler
version, exit status and test output before calling a runtime check passed.
Unavailable images, compilers or daemons mean `not_run`, never a passing test.

## Reviews of other projects

Use the project's relevant existing tests or focused benign regression checks
inside an available disposable container. Keep source revisions and before/after
reports immutable. A passing smoke fixture does not validate another project's
behavior. Never run downloaded project scripts on the host or install a runtime
automatically. See the [remediation workflow](../skills/hindsight-triage/references/remediation.md).

As of this local preparation, no Docker/Podman executable was available and the
runtime tests were not executed. The source-only known-answer trials are useful
workflow checks but do not establish detection quality.
