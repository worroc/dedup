import clickclick as cc

from .context import ctx


def parameterized(func):
    def wrapper(msg, **kwargs):
        if kwargs:
            params = " ".join([f"{k}={v}" for (k, v) in sorted(kwargs.items())])
            msg = f"{msg} {params}"
        func(msg)

    return wrapper


@parameterized
def debug(msg):
    if ctx.verbose:
        cc.secho(msg, fg="bright_black", bold=False)


@parameterized
def info(msg):
    cc.info(msg)


@parameterized
def error(msg):
    cc.error(msg)


@parameterized
def warning(msg):
    cc.warning(msg)


@parameterized
def ok(msg):
    cc.ok(msg)
