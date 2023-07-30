/// <reference types="types-for-adobe/Photoshop/2015.5"/>

var scriptVersion = "1.0.0";
var scriptName = {
    en: "AzurLaneTachieHelper PNG Export",
};

var defaultSettings = {
    paintingfaceFolder: "face",
};

function collectLayers(group: LayerSet, pattern: (arg0: Layer) => boolean): Array<Layer> {
    var layers = new Array();
    for (var i = 0; i < group.artLayers.length; i++) {
        var layer = group.artLayers[i];
        if (pattern(layer)) {
            layers.push(layer);
            layer.visible = false;
        }
    }
    return layers;
}

function savePng(name: string) {
    var file = new File(`${name}.png`);
    file.parent.create();
    if (file.exists) file.remove();
    app.activeDocument.saveAs(file, opts, true, Extension.LOWERCASE);
}

if (app.documents.length == 0) {
    alert("No documents available");
} else {
    var root = app.activeDocument.path.fsName.replace(/\\/g, "/");
    var PaintingName = app.activeDocument.name.split(".")[0];
    var PaintingGroup = app.activeDocument.layerSets.getByName("painting");
    var PaintingfaceGroup = app.activeDocument.layerSets.getByName("paintingface");

    var PaintingLayers = collectLayers(
        PaintingGroup,
        (layer: Layer) => layer.name.indexOf(PaintingName) == 0
    );
    var PaintingfaceLayers = collectLayers(
        PaintingfaceGroup,
        (layer: Layer) => /^(0|([1-9][0-9]*))$/.test(layer.name)
    );

    var opts = new PNGSaveOptions();
    opts.compression = 6;

    for (var i = 0; i < PaintingLayers.length; i++) {

        var layer = PaintingLayers[i];
        layer.visible = true;
        savePng(`${root}/${layer.name}`);
        layer.visible = false;
    }

    for (var i = 0; i < PaintingfaceLayers.length; i++) {
        var layer = PaintingfaceLayers[i];
        layer.visible = true;
        savePng(`${root}/${defaultSettings.paintingfaceFolder}/${layer.name}`);
        layer.visible = false;
    }

    for (var i = 0; i < PaintingLayers.length; i++) PaintingLayers[i].visible = true;
}
