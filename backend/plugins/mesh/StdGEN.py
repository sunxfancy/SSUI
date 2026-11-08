"""Lazy entry points for the bundled canonicalization and multiview pipeline."""


def canonicalize(*args, **kwargs):
    from stdgen.pipeline import canonicalize as implementation
    return implementation(*args, **kwargs)


def multiview(*args, **kwargs):
    from stdgen.pipeline import multiview as implementation
    return implementation(*args, **kwargs)
