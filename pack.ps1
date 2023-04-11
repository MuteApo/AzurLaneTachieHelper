rm -recurse dist\AzurLaneTachieHelper\*

$EnvDir = -Split $(conda env list | findstr "*")
$UnityPyData = $EnvDir[2] + "\Lib\site-packages\UnityPy\resources\uncompressed.tpk"

$App = @{
    AzurLaneTachieViewer = "viewer.py";
    AzurLaneTachieEncoder = "encoder.py";
    AzurLaneTachieDecoder = "decoder.py";
    AzurLaneTachieMerger = "merger.py";
    AzurLaneTachieSplitter = "splitter.py";
}

$App.GetEnumerator().ForEach({
    $name = $_.key
    $src = $_.value
    pyinstaller -Fy $src -n $name -i ico\cheshire.ico --onedir --add-data $UnityPyData";"UnityPy\resources
    Copy-Item -Recurse -Force dist\$name\* dist\AzurLaneTachieHelper
    Remove-Item -Recurse dist\$name
})

pyinstaller -Fw viewer.py -n AzurLaneTachieViewer -i ico\cheshire.ico --onefile --add-data $UnityPyData";"UnityPy\resources