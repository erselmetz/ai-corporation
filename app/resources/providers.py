"""Accounting-only internal model buckets, separate from selectable chat providers."""
class ResourceProviderRegistry:
    def __init__(self,providers):self.providers=providers;self.internal={'local-speech':object(),'local-embedding':object()}
    def get(self,identifier):
        if identifier in self.internal:return self.internal[identifier]
        return self.providers.get(identifier)
    def all(self):return {**self.providers.all(),**self.internal}
    def exists(self,identifier):return identifier in self.internal or self.providers.exists(identifier)
