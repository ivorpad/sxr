/* Local protocol shared with sxr.worker_protocol; no third-party libraries. */
#ifndef SXR_CLIENT_H
#define SXR_CLIENT_H
#include <stddef.h>
#ifndef SXR_VERSION
#error SXR_VERSION must match the bundled Python package
#endif
int worker_connect(const char *path);
int worker_request(int fd, const char *action, int argc, char **argv);
int worker_response(int fd);
#endif
