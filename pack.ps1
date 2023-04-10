pyinstaller -Fwy viewer.py -n AzurLaneTachieViewer -i ico/cheshire.ico --onedir --add-data ico/cheshire.ico";"ico
mv dist/AzurLaneTachieViewer dist/AzurLaneTachieHelper

pyinstaller -Fwy encoder.py -n AzurLaneTachieEncoder -i ico/cheshire.ico --onedir --add-data ico/cheshire.ico";"ico
cp dist/AzurLaneTachieEncoder/AzurLaneTachieEncoder.exe dist/AzurLaneTachieHelper
rm -r dist/AzurLaneTachieEncoder

pyinstaller -Fwy decoder.py -n AzurLaneTachieDecoder -i ico/cheshire.ico --onedir --add-data ico/cheshire.ico";"ico
cp dist/AzurLaneTachieDecoder/AzurLaneTachieDecoder.exe dist/AzurLaneTachieHelper
rm -r dist/AzurLaneTachieDecoder

pyinstaller -Fw viewer.py -n AzurLaneTachieViewer -i ico/cheshire.ico --onefile