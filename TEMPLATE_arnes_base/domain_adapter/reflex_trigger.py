"""
<DOMAIN> instance — reflex trigger.

Fill in: the one condition that bypasses the budget entirely, if this
domain has one (Touch, by convention). If it doesn't, don't force one
— set HAS_REFLEX = False and leave reflex_trigger() unused.
"""

HAS_REFLEX = None  # set True or False explicitly — don't leave unset


def reflex_trigger(*args, **kwargs):
    raise NotImplementedError("reflex_trigger(): define the bypass condition here, "
                               "or set HAS_REFLEX = False if this domain has none")
