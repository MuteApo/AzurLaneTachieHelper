from .AssetManager import AssetManager

from .TextureHelper import TextureHelper


class PaintingHelper(TextureHelper):
    def __init__(self, asset_manager: AssetManager):
        super().__init__()
        self.asset_manager = asset_manager

    @property
    def metas(self):
        return self.asset_manager.metas

    @property
    def deps(self):
        return self.asset_manager.deps

    @property
    def name(self):
        return self.asset_manager.name

    @property
    def size(self):
        return self.asset_manager.size
