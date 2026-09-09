/* Bounded requests and streamed output for the owner-only Unix socket. */
#include "client.h"
#include <arpa/inet.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <unistd.h>

static int transfer(int fd, void *buffer, size_t length, int writing) {
    char *cursor = buffer;
    while (length) {
        ssize_t n = writing ? write(fd, cursor, length) : read(fd, cursor, length);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) return -1;
        cursor += n;
        length -= (size_t)n;
    }
    return 0;
}

static int number(int fd, uint32_t value) {
    value = htonl(value);
    return transfer(fd, &value, sizeof value, 1);
}

static int field(int fd, const char *value, size_t *budget) {
    size_t size = value ? strlen(value) : 0;
    *budget += size;
    if (size > 1024 * 1024 || *budget > 4 * 1024 * 1024) return -1;
    if (number(fd, value ? (uint32_t)size : UINT32_MAX)) return -1;
    return transfer(fd, (void *)value, size, 1);
}

int worker_connect(const char *path) {
    struct stat info;
    struct sockaddr_un address = {0};
    if (strlen(path) >= sizeof address.sun_path || lstat(path, &info) ||
        !S_ISSOCK(info.st_mode) || info.st_uid != getuid() || (info.st_mode & 077))
        return -1;
    address.sun_family = AF_UNIX;
    strcpy(address.sun_path, path);
    int fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd >= 0 && connect(fd, (struct sockaddr *)&address, sizeof address)) {
        close(fd);
        return -1;
    }
    return fd;
}

int worker_request(int fd, int argc, char **argv) {
    const char *keys[] = {"HOME", "PATH", "SXR_CACHE_DIR", "SXR_NO_CACHE", "XDG_CACHE_HOME",
        "CODEX_HOME", "CLAUDE_CONFIG_DIR", "CODEX_THREAD_ID", "CODEX_SESSION_ID", "TZ"};
    char *cwd = getcwd(NULL, 0);
    size_t budget = 0;
    if (!cwd || argc > 4096) { free(cwd); return -1; }
    int failed = field(fd, SXR_VERSION, &budget) || field(fd, "find", &budget) ||
        field(fd, cwd, &budget) || number(fd, (uint32_t)argc);
    free(cwd);
    if (failed) return -1;
    for (int i = 0; i < argc; i++)
        if (field(fd, argv[i], &budget)) return -1;
    unsigned count = sizeof keys / sizeof *keys;
    if (number(fd, count)) return -1;
    for (unsigned i = 0; i < count; i++)
        if (field(fd, keys[i], &budget) || field(fd, getenv(keys[i]), &budget)) return -1;
    return 0;
}

int worker_response(int fd) {
    char buffer[16384], kind;
    uint32_t size, code;
    while (!transfer(fd, &kind, 1, 0) && !transfer(fd, &size, 4, 0)) {
        size = ntohl(size);
        if (kind == 'R') {
            if (size != 4 || transfer(fd, &code, 4, 0) || ntohl(code) > 255) break;
            return (int)ntohl(code);
        }
        if ((kind != 'O' && kind != 'E') || size > sizeof buffer) break;
        if (transfer(fd, buffer, size, 0) ||
            transfer(kind == 'O' ? STDOUT_FILENO : STDERR_FILENO, buffer, size, 1)) break;
    }
    fputs("error: search worker disconnected; rerun the command\n", stderr);
    return 2;
}
