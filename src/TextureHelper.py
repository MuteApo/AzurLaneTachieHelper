from .AssetManager import AssetManager


class TextureHelper:
    def __init__(self, asset_manager: AssetManager):
        super().__init__()
        self.asset_manager = asset_manager

    @property
    def meta(self):
        return self.asset_manager.meta

    @property
    def name(self):
        return self.asset_manager.name

    @property
    def size(self):
        return self.asset_manager.size

    @property
    def bias(self):
        return self.asset_manager.bias

    @property
    def deps(self):
        return self.asset_manager.deps

    @property
    def layers(self):
        return self.asset_manager.layers

    @property
    def face_layer(self):
        return self.asset_manager.layers["face"]

    @property
    def faces(self):
        return self.asset_manager.faces

    @property
    def repls(self):
        return self.asset_manager.repls
