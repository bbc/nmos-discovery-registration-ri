try:
    import avahi
except:
    from bonjour import MDNSEngine
else:
    from avahidbus import MDNSEngine

__all__ = [ "MDNSEngine" ]
