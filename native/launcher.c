/* Relocatable launcher: reuse a warm search worker, exec the bundled CLI otherwise. */
#include "client.h"
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#ifdef __APPLE__
#include <mach-o/dyld.h>
#endif

static int backend(char *result, size_t size) {
    char executable[PATH_MAX], resolved[PATH_MAX];
#ifdef __APPLE__
    uint32_t length = sizeof executable;
    if (_NSGetExecutablePath(executable, &length)) return -1;
#else
    ssize_t length = readlink("/proc/self/exe", executable, sizeof executable - 1);
    if (length < 0) return -1;
    executable[length] = '\0';
#endif
    if (!realpath(executable, resolved)) return -1;
    char *slash = strrchr(resolved, '/');
    if (!slash) return -1;
    *slash = '\0';
    int n = snprintf(result, size, "%s/sxr-python", resolved);
    return n < 0 || (size_t)n >= size ? -1 : 0;
}

static int socket_name(char *result, size_t size) {
    const char *root = getenv("SXR_CACHE_DIR");
    const char *suffix = "";
    if (!root || !*root) {
        root = getenv("XDG_CACHE_HOME");
        suffix = "/sxr";
        if (!root || !*root) {
            root = "~/.cache";
        }
    }
    const char *home = "";
    if (root[0] == '~' && (root[1] == '/' || !root[1])) {
        home = getenv("HOME");
        if (!home || !*home) return -1;
        root++;
    } else if (root[0] != '/') {
        /* Python handles relative paths and ~user expansion without stale cwd state. */
        return -1;
    }
    int n = snprintf(result, size, "%s%s%s/find-%s.sock", home, root, suffix, SXR_VERSION);
    return n < 0 || (size_t)n >= size ? -1 : 0;
}

static pid_t start_worker(const char *script, const char *path) {
    pid_t child = fork();
    if (child < 0) return -1;
    if (!child) {
        if (setsid() < 0) _exit(1);
        int null = open("/dev/null", O_RDWR);
        if (null < 0) _exit(1);
        for (int fd = 0; fd <= 2; fd++)
            if (dup2(null, fd) < 0) _exit(1);
        if (null > 2) close(null);
        execl(script, script, "serve", "--foreground", path, (char *)NULL);
        _exit(1);
    }
    return child;
}

int main(int argc, char **argv) {
    char script[PATH_MAX], path[104];
    if (backend(script, sizeof script)) {
        fputs("error: cannot locate bundled sxr-python\n", stderr);
        return 2;
    }
    const char *disabled = getenv("SXR_NO_DAEMON");
    if (argc > 1 && (!strcmp(argv[1], "find") || !strcmp(argv[1], "skills")) &&
        (!disabled || strcmp(disabled, "1")) &&
        !socket_name(path, sizeof path)) {
        signal(SIGPIPE, SIG_IGN);
        int fd = worker_connect(path);
        if (fd < 0 && errno != EACCES && errno != EPERM) {
            pid_t child = start_worker(script, path);
            for (int i = 0; i < 100 && fd < 0; i++) {
                if (child < 0 || waitpid(child, NULL, WNOHANG) == child) break;
                struct timespec delay = {0, 10000000};
                nanosleep(&delay, NULL);
                fd = worker_connect(path);
                if (fd < 0 && (errno == EACCES || errno == EPERM)) break;
            }
        }
        if (fd >= 0) {
            if (worker_request(fd, argv[1], argc - 2, argv + 2)) {
                close(fd);
                fputs("error: cannot send search request\n", stderr);
                return 2;
            }
            int code = worker_response(fd);
            close(fd);
            return code;
        }
        signal(SIGPIPE, SIG_DFL);
    }
    argv[0] = script;
    execv(script, argv);
    perror("error: cannot execute bundled sxr-python");
    return 2;
}
