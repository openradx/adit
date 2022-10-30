import socket

fullstack = None


def is_fullstack():
    global fullstack

    if fullstack is None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            fullstack = not bool(sock.connect(("rabbit", 5672)))
        except:  # noqa
            fullstack = False

    return fullstack
