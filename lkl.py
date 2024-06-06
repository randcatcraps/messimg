"""
LKL binding for Python
"""

import ctypes as _ctypes
import dataclasses as _dataclasses
import typing as _typing


class LklBindingError(Exception):
    """
    errno wrapper for LKL functions
    """

    def __init__(self, _strerror: str):
        Exception.__init__(self, _strerror)


# void (*)(const char *str, int len)
_CLklPrintCallback = _ctypes.CFUNCTYPE(None, _ctypes.c_char_p, _ctypes.c_int)

# void (*)(void)
_CLklPanicCallback = _ctypes.CFUNCTYPE(None)


# struct {
#     const char *virtio_devices;
#     void (*print)(const char *str, int len);
#     void (*panic)(void);
#     ...
# }
class _CLklHostOperations(_ctypes.Structure):
    # pylint: disable=too-few-public-methods

    _fields_ = [
        ('_reserved', _ctypes.POINTER(_ctypes.c_char)),
        ('print_', _CLklPrintCallback),
        ('panic', _CLklPanicCallback),
    ]


@_dataclasses.dataclass
class LklHostOperations:
    # pylint: disable=too-few-public-methods
    """
    host callbacks for LKL
    """

    # for _CLklPrintCallback
    print_: _typing.Callable[[bytes], None] | None = None
    # for _CLklPanicCallback
    panic: _typing.Callable[[], None] | None = None


# pylint: disable=invalid-name
_g_lkl_instantiated = False


class LKL:
    """
    LKL wrapper
    """

    def __init__(self, dll_path: str,
                 cmdline: str,
                 host_ops: LklHostOperations | None = None):
        # pylint: disable=global-statement
        global _g_lkl_instantiated

        self._initialized_lkl = False
        if _g_lkl_instantiated:
            raise TypeError('LKL can only be instantiated once')
        self._dll = _ctypes.CDLL(dll_path)
        _g_lkl_instantiated = True

        # function

        # const char *lkl_strerror(int err)
        self._dll.lkl_strerror.restype = _ctypes.c_char_p
        self._dll.lkl_strerror.argtypes = [_ctypes.c_int]

        # int lkl_init(struct lkl_host_operations *lkl_ops)
        self._dll.lkl_init.restype = _ctypes.c_int
        self._dll.lkl_init.errcheck = self._chk_lkl_cfunc_ret
        self._dll.lkl_init.argtypes = [_ctypes.POINTER(_CLklHostOperations)]

        # void lkl_cleanup(void)
        self._dll.lkl_cleanup.restype = None
        self._dll.lkl_cleanup.argtypes = []

        # int lkl_start_kernel(const char *cmd_line, ...)
        self._dll.lkl_start_kernel.restype = _ctypes.c_int
        self._dll.lkl_start_kernel.errcheck = self._chk_lkl_cfunc_ret
        self._dll.lkl_start_kernel.argtypes = [_ctypes.c_char_p]

        # int lkl_is_running(void)
        self._dll.lkl_is_running.restype = _ctypes.c_int
        self._dll.lkl_is_running.argtypes = []

        # long lkl_sys_halt(void)
        self._dll.lkl_sys_halt.restype = _ctypes.c_long
        self._dll.lkl_sys_halt.errcheck = self._chk_lkl_cfunc_ret
        self._dll.lkl_sys_halt.argtypes = []

        # variables

        # struct lkl_host_operations lkl_host_ops
        self._lkl_host_ops = _CLklHostOperations.in_dll(self._dll,
                                                        'lkl_host_ops')

        # initialize LKL

        if host_ops:
            if host_ops.print_:
                self._lkl_host_ops.print_ = _CLklPrintCallback(
                    lambda str_, len_: host_ops.print_(str_[:len_])
                )
            if host_ops.panic:
                self._lkl_host_ops.panic = _CLklPanicCallback(host_ops.panic)
        cmdline_ = cmdline.encode()

        self._dll.lkl_init(self._lkl_host_ops)
        self._initialized_lkl = True
        self._dll.lkl_start_kernel(cmdline_)

    def _chk_lkl_cfunc_ret(self, ret: int, *_):
        if ret < 0:
            raise LklBindingError(self._dll.lkl_strerror(ret))

    def __del__(self):
        if not self._initialized_lkl:
            return

        if self._dll.lkl_is_running():
            self._dll.lkl_sys_halt()

        self._dll.lkl_cleanup()
