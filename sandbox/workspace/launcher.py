"""Trusted bootstrap: enter a credential-free root, drop privilege, restrict syscalls.

Only this reviewed launcher starts with chroot/setuid capabilities. Candidate code
is imported after all restrictions succeed. No fallback to unrestricted execution.
"""

import asyncio
import ctypes
import errno
import os
import resource
import socket

import uvicorn


def restrict():
    libc = ctypes.CDLL(None, use_errno=True)
    sec = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    sec.seccomp_init.restype = ctypes.c_void_p
    sec.seccomp_init.argtypes = [ctypes.c_uint32]
    sec.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    sec.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    sec.seccomp_load.argtypes = [ctypes.c_void_p]
    sec.seccomp_release.argtypes = [ctypes.c_void_p]
    context = sec.seccomp_init(0x7FFF0000)
    if not context:
        raise RuntimeError("seccomp_unavailable")
    try:
        # Threads are needed by FastAPI's sync handlers; clone is constrained below.
        denied = (
            "socket",
            "socketpair",
            "connect",
            "execve",
            "execveat",
            "fork",
            "vfork",
            "ptrace",
            "mount",
            "umount2",
            "pivot_root",
            "chroot",
            "setns",
            "unshare",
            "bpf",
            "userfaultfd",
            "keyctl",
            "add_key",
            "request_key",
            "open_by_handle_at",
            "init_module",
            "finit_module",
            "delete_module",
            "reboot",
            "kexec_load",
            "process_vm_readv",
            "process_vm_writev",
            "pidfd_getfd",
            "perf_event_open",
        )
        for name in denied:
            number = sec.seccomp_syscall_resolve_name(name.encode())
            if number >= 0 and sec.seccomp_rule_add(context, 0x50000 | errno.EPERM, number, 0):
                raise RuntimeError("seccomp_rule_failed")
        # Force glibc's clone3 fallback; clone3's pointer arguments cannot be filtered.
        number = sec.seccomp_syscall_resolve_name(b"clone3")
        if number >= 0 and sec.seccomp_rule_add(context, 0x50000 | errno.ENOSYS, number, 0):
            raise RuntimeError("seccomp_rule_failed")

        class Compare(ctypes.Structure):
            _fields_ = [
                ("arg", ctypes.c_uint),
                ("op", ctypes.c_uint),
                ("a", ctypes.c_uint64),
                ("b", ctypes.c_uint64),
            ]

        sec.seccomp_rule_add_array.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_int,
            ctypes.c_uint,
            ctypes.POINTER(Compare),
        ]
        # SCMP_CMP_MASKED_EQ: reject clone without CLONE_THREAD (0x10000).
        rule = Compare(0, 7, 0x10000, 0)
        if sec.seccomp_rule_add_array(
            context,
            0x50000 | errno.EPERM,
            sec.seccomp_syscall_resolve_name(b"clone"),
            1,
            ctypes.byref(rule),
        ):
            raise RuntimeError("seccomp_clone_failed")
        if libc.prctl(38, 1, 0, 0, 0) != 0 or sec.seccomp_load(context):
            raise RuntimeError("seccomp_load_failed")
    finally:
        sec.seccomp_release(context)


def main():
    if os.getuid() != 0:
        raise RuntimeError("trusted_bootstrap_requires_chroot_capability")
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("0.0.0.0", 8000))
    listener.listen(128)
    loop = asyncio.new_event_loop()  # Creates its self-pipe before the syscall filter.
    asyncio.set_event_loop(loop)
    # No descriptor may keep an escape route to the original filesystem.
    permitted = {
        0,
        1,
        2,
        listener.fileno(),
        loop._ssock.fileno(),
        loop._csock.fileno(),
        loop._selector.fileno(),
    }
    for name in os.listdir("/proc/self/fd"):
        fd = int(name)
        if fd not in permitted:
            try:
                os.close(fd)
            except OSError:
                pass
    os.chroot("/jail")
    os.chdir("/app")
    os.setgroups([])
    os.setgid(10001)
    os.setuid(10001)
    os.environ.clear()
    os.environ.update({"LEDGERLITE_DB": "/tmp/ledgerlite.sqlite3", "PYTHONDONTWRITEBYTECODE": "1"})
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024 * 1024, 16 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    restrict()
    # Admission probes execute before any candidate import, on every provider/job.
    denied = 0
    for operation in (
        lambda: socket.socket(),
        lambda: os.setuid(0),
        lambda: os.open("/outside-marker", os.O_RDONLY),
        lambda: os.open("/var/run/secrets/kubernetes.io/serviceaccount/token", os.O_RDONLY),
        lambda: os.execve("/bin/true", ["true"], {}),
    ):
        try:
            operation()
        except OSError:
            denied += 1
    if denied != 5 or os.getuid() != 10001:
        raise RuntimeError("isolation_probe_failed")
    import sys

    sys.path.insert(0, "/app")
    config = uvicorn.Config(
        "app:app", host="0.0.0.0", port=8000, loop="asyncio", access_log=False, log_level="warning"
    )
    print("PROOFLOOP_ISOLATION=chroot_uid_seccomp_v1", flush=True)
    loop.run_until_complete(uvicorn.Server(config).serve(sockets=[listener]))


if __name__ == "__main__":
    main()
