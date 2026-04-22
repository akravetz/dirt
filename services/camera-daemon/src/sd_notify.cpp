#include "sd_notify.hpp"

#include <cstddef>
#include <cstdlib>
#include <cstring>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

namespace dirt {

namespace {
int g_fd = -1;
sockaddr_un g_addr{};
socklen_t g_addrlen = 0;
} // namespace

void notify_init() {
    const char* path = std::getenv("NOTIFY_SOCKET");
    if (!path || !*path) return; // not running under systemd Type=notify

    g_fd = ::socket(AF_UNIX, SOCK_DGRAM | SOCK_CLOEXEC, 0);
    if (g_fd < 0) return;

    size_t path_len = std::strlen(path);
    if (path_len >= sizeof(g_addr.sun_path)) {
        ::close(g_fd); g_fd = -1; return;
    }

    g_addr.sun_family = AF_UNIX;
    if (path[0] == '@') {
        // Linux abstract socket: first byte NUL, rest is the name (no trailing NUL).
        g_addr.sun_path[0] = '\0';
        std::memcpy(g_addr.sun_path + 1, path + 1, path_len - 1);
        g_addrlen = static_cast<socklen_t>(offsetof(sockaddr_un, sun_path) + path_len);
    } else {
        std::memcpy(g_addr.sun_path, path, path_len);
        g_addr.sun_path[path_len] = '\0';
        g_addrlen = sizeof(sockaddr_un);
    }
}

void notify_send(const std::string& msg) {
    if (g_fd < 0) return;
    ::sendto(g_fd, msg.data(), msg.size(), MSG_NOSIGNAL,
             reinterpret_cast<sockaddr*>(&g_addr), g_addrlen);
}

} // namespace dirt
