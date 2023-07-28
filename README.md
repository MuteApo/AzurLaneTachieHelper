### 碧蓝航线立绘助手 AzurLaneTachieHelper

#### Features

- Unpack & pack painting
- Merge & split paintingface 
- Support multi-layers
- Dump as photoshop document (i.e. psd)

#### Building Dependencies

- Python 3.10 with following libraries:
  - NumPy
  - Pillow
  - Pytoshop
  - UnityPy
- Or with given env spec:
  - Conda
    ```shell
    conda env create -f environment.yml
    ```
  - Pypi
    ```shell
    pip install -r requirements.txt
    ```
- Build app
  - pyinstaller
    ```shell
    python build.py --pyinstaller/-p
    ```
  - nuitka (C++ compiler required, eg. msvc, gcc, clang, etc.)
    ```shell
    python build.py --nuitka/-n
    ```